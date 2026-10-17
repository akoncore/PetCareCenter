from datetime import timedelta
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from apps.users.models import CustomUser
from apps.clinics.models import Clinic, ClinicMembership
from apps.pets.models import Pet
from .models import Service, Appointment, TransportRequest


class BookingMvpTests(TestCase):
    def setUp(self):
        self.owner = CustomUser.objects.create_user("owner@example.com", "Pet", "Owner", "StrongPassword444!")
        self.other = CustomUser.objects.create_user("other@example.com", "Other", "User", "StrongPassword444!")
        self.admin = CustomUser.objects.create_user("admin@example.com", "Clinic", "Admin", "StrongPassword444!")
        self.driver = CustomUser.objects.create_user("driver@example.com", "Clinic", "Driver", "StrongPassword444!")
        self.clinic = Clinic.objects.create(
            name="Demo", email="clinic@example.com", address="Example 1", city="Almaty"
        )
        ClinicMembership.objects.create(user=self.admin, clinic=self.clinic, role="clinic_admin")
        ClinicMembership.objects.create(user=self.driver, clinic=self.clinic, role="clinic_transport")
        self.pet = Pet.objects.create(owner=self.owner, clinic=self.clinic, name="Luna", species="cat")
        self.service = Service.objects.create(clinic=self.clinic, name="Checkup", duration_minutes=45)
        self.slot = (timezone.now() + timedelta(days=2)).replace(second=0, microsecond=0)
        self.client = APIClient()
        self.client.force_authenticate(self.owner)

    def payload(self, at=None):
        return {
            "clinic": self.clinic.pk, "pet": str(self.pet.pk),
            "service": self.service.pk, "starts_at": (at or self.slot).isoformat(),
        }

    def book(self):
        result = self.client.post("/api/appointments/", self.payload())
        self.assertEqual(result.status_code, 201, result.data)
        return result.data["id"]

    def test_overlapping_slots_rejected_even_when_starts_differ(self):
        self.book()
        other = self.client.post(
            "/api/appointments/", self.payload(self.slot + timedelta(minutes=15))
        )
        self.assertEqual(other.status_code, 400)

    def test_booking_other_users_pet_is_rejected(self):
        self.client.force_authenticate(self.other)
        self.assertEqual(self.client.post("/api/appointments/", self.payload()).status_code, 400)

    def test_other_owner_cannot_read_booking(self):
        booking_id = self.book()
        self.client.force_authenticate(self.other)
        self.assertEqual(self.client.get(f"/api/appointments/{booking_id}/").status_code, 404)

    def test_owner_reschedules(self):
        booking_id = self.book()
        new_slot = self.slot + timedelta(hours=3)
        changed = self.client.post(
            f"/api/appointments/{booking_id}/reschedule/",
            {"starts_at": new_slot.isoformat()},
        )
        self.assertEqual(changed.status_code, 200, changed.data)

    def test_clinic_admin_manages_service_owner_cannot(self):
        self.assertEqual(self.client.post("/api/services/", {
            "clinic": self.clinic.pk, "name": "New", "duration_minutes": 20,
        }).status_code, 403)
        self.client.force_authenticate(self.admin)
        self.assertEqual(self.client.post("/api/services/", {
            "clinic": self.clinic.pk, "name": "New", "duration_minutes": 20,
        }).status_code, 201)

    def test_full_transport_workflow_and_permissions(self):
        booking_id = self.book()
        created = self.client.post("/api/transport/", {
            "appointment": booking_id, "pickup_address": "Example 2", "contact_phone": "+77000000000",
        })
        self.assertEqual(created.status_code, 201, created.data)
        transport_id = created.data["id"]
        self.assertEqual(self.client.post(
            f"/api/transport/{transport_id}/advance/",
            {"status": "confirmed", "assigned_driver": self.driver.pk}
        ).status_code, 403)
        self.client.force_authenticate(self.admin)
        self.assertEqual(self.client.post(
            f"/api/transport/{transport_id}/advance/",
            {"status": "confirmed", "assigned_driver": self.driver.pk}
        ).status_code, 200)
        self.client.force_authenticate(self.driver)
        for state in ["picked_up", "at_clinic", "returning", "completed"]:
            result = self.client.post(f"/api/transport/{transport_id}/advance/", {"status": state})
            self.assertEqual(result.status_code, 200, result.data)
        self.client.force_authenticate(self.owner)
        self.assertEqual(
            self.client.get(f"/api/transport/{transport_id}/").data["status"], "completed"
        )
        self.assertEqual(
            self.client.post(f"/api/appointments/{booking_id}/cancel/").status_code, 400
        )
