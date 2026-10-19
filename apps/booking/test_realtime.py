from datetime import timedelta
from unittest.mock import patch

from channels.db import database_sync_to_async
from channels.layers import get_channel_layer
from channels.testing import WebsocketCommunicator
from django.db import transaction
from django.test import TransactionTestCase, override_settings
from django.utils import timezone
from redis.exceptions import ConnectionError
from rest_framework.authtoken.models import Token

from apps.clinics.models import Clinic, ClinicMembership
from apps.pets.models import Pet
from apps.users.models import CustomUser
from settings.asgi import application
from .models import Appointment, Service, TransportRequest


class RealtimeTests(TransactionTestCase):
    """Exercise actual Redis channel delivery, not an in-memory channel layer."""

    def setUp(self):
        self.owner = CustomUser.objects.create(email="owner@example.com")
        self.other = CustomUser.objects.create(email="other@example.com")
        self.staff = CustomUser.objects.create(email="staff@example.com")
        self.driver = CustomUser.objects.create(email="driver@example.com")
        self.owner_token = Token.objects.create(user=self.owner).key
        self.other_token = Token.objects.create(user=self.other).key
        self.staff_token = Token.objects.create(user=self.staff).key
        self.driver_token = Token.objects.create(user=self.driver).key
        self.clinic = Clinic.objects.create(name="Demo", email="clinic@example.com", city="Almaty", address="Street")
        self.membership = ClinicMembership.objects.create(user=self.staff, clinic=self.clinic, role="clinic_staff")
        ClinicMembership.objects.create(user=self.driver, clinic=self.clinic, role="clinic_transport")
        self.pet = Pet.objects.create(owner=self.owner, clinic=self.clinic, name="Luna", species="cat")
        self.service = Service.objects.create(clinic=self.clinic, name="Checkup")
        self.appointment = Appointment.objects.create(
            clinic=self.clinic, owner=self.owner, pet=self.pet, service=self.service,
            starts_at=timezone.now() + timedelta(days=1),
        )
        self.transport = TransportRequest.objects.create(
            appointment=self.appointment, assigned_driver=self.driver,
            pickup_address="Private address", contact_phone="Private phone",
        )

    def socket(self, resource="appointments", origin=b"http://localhost:8000"):
        pk = self.appointment.pk if resource == "appointments" else self.transport.pk
        return WebsocketCommunicator(application, f"/ws/{resource}/{pk}/", headers=[(b"origin", origin)])

    async def authenticate(self, socket, token):
        self.assertTrue((await socket.connect())[0])
        await socket.send_json_to({"type": "authenticate", "token": token})
        return await socket.receive_json_from(timeout=3)

    async def test_owner_receives_committed_change_via_redis(self):
        socket = self.socket()
        try:
            self.assertEqual((await self.authenticate(socket, self.owner_token))["type"], "ready")

            @database_sync_to_async
            def update():
                with transaction.atomic():
                    self.appointment.status = Appointment.Status.CANCELLED
                    self.appointment.save()

            await update()
            self.assertEqual(await socket.receive_json_from(timeout=3), {
                "type": "changed", "resource": "appointment", "id": self.appointment.pk,
            })
            await socket.send_json_to({"type": "ping"})
            self.assertEqual(await socket.receive_json_from(), {"type": "pong"})
        finally:
            await socket.disconnect()

    async def test_other_owner_is_denied(self):
        socket = self.socket()
        try:
            await socket.connect()
            await socket.send_json_to({"type": "authenticate", "token": self.other_token})
            self.assertEqual((await socket.receive_output())["code"], 4403)
        finally:
            await socket.disconnect()

    async def test_idle_socket_survives_redis_blocking_read_timeout(self):
        socket = self.socket()
        try:
            await self.authenticate(socket, self.owner_token)
            # Exceed the channel layer's 5s blocking receive and exercise its next poll.
            self.assertTrue(await socket.receive_nothing(timeout=5.5))
            await socket.send_json_to({"type": "ping"})
            self.assertEqual(await socket.receive_json_from(), {"type": "pong"})
            await get_channel_layer().group_send(f"appointment.{self.appointment.pk}", {"type": "resource.changed"})
            self.assertEqual((await socket.receive_json_from(timeout=3))["type"], "changed")
        finally:
            await socket.disconnect()

    async def test_untrusted_origin_is_denied(self):
        socket = self.socket(origin=b"https://untrusted.example")
        self.assertFalse((await socket.connect())[0])
        await socket.disconnect()

    async def test_invalid_token_is_denied(self):
        socket = self.socket()
        try:
            await socket.connect()
            await socket.send_json_to({"type": "authenticate", "token": "0" * 40})
            self.assertEqual((await socket.receive_output())["code"], 4401)
        finally:
            await socket.disconnect()

    @override_settings(WEBSOCKET_AUTH_TIMEOUT=0.02)
    async def test_missing_authentication_times_out(self):
        socket = self.socket()
        try:
            await socket.connect()
            self.assertEqual((await socket.receive_output())["code"], 4401)
        finally:
            await socket.disconnect()

    async def test_malformed_payload_closes_cleanly(self):
        socket = self.socket()
        try:
            await socket.connect()
            await socket.send_to(text_data="[not-json")
            self.assertEqual((await socket.receive_output())["code"], 4400)
        finally:
            await socket.disconnect()

    async def test_logout_revokes_subscription_before_next_event(self):
        socket = self.socket()
        try:
            await self.authenticate(socket, self.owner_token)
            await database_sync_to_async(Token.objects.filter(user=self.owner).delete)()
            await get_channel_layer().group_send(f"appointment.{self.appointment.pk}", {"type": "resource.changed"})
            self.assertEqual((await socket.receive_output(timeout=3))["code"], 4401)
        finally:
            await socket.disconnect()

    async def test_removed_membership_revokes_access(self):
        socket = self.socket()
        try:
            await self.authenticate(socket, self.staff_token)
            await database_sync_to_async(ClinicMembership.objects.filter(pk=self.membership.pk).update)(is_active=False)
            await get_channel_layer().group_send(f"appointment.{self.appointment.pk}", {"type": "resource.changed"})
            self.assertEqual((await socket.receive_output(timeout=3))["code"], 4403)
        finally:
            await socket.disconnect()

    async def test_assigned_driver_receives_transport_change_but_not_appointment(self):
        socket = self.socket("transport")
        denied = self.socket()
        try:
            await self.authenticate(socket, self.driver_token)
            self.transport.status = TransportRequest.Status.CONFIRMED
            await database_sync_to_async(self.transport.save)()
            self.assertEqual(await socket.receive_json_from(timeout=3), {
                "type": "changed", "resource": "transport", "id": self.transport.pk,
            })
            await denied.connect()
            await denied.send_json_to({"type": "authenticate", "token": self.driver_token})
            self.assertEqual((await denied.receive_output())["code"], 4403)
        finally:
            await socket.disconnect()
            await denied.disconnect()

    def test_transaction_rollback_does_not_publish(self):
        with patch("apps.booking.events.publish_change") as publish:
            with self.assertRaises(RuntimeError):
                with transaction.atomic():
                    self.appointment.save()
                    raise RuntimeError("rollback")
            publish.assert_not_called()

    def test_notification_is_sent_only_after_commit(self):
        with patch("apps.booking.events.publish_change") as publish:
            with transaction.atomic():
                self.appointment.save()
                publish.assert_not_called()
            publish.assert_called_once_with("appointment", self.appointment.pk)

    def test_redis_failure_does_not_undo_successful_database_save(self):
        with patch("apps.booking.events.get_channel_layer", side_effect=ConnectionError("offline")):
            with self.assertLogs("petcare.realtime", level="ERROR"):
                self.appointment.status = Appointment.Status.CANCELLED
                self.appointment.save()
        self.appointment.refresh_from_db()
        self.assertEqual(self.appointment.status, Appointment.Status.CANCELLED)
