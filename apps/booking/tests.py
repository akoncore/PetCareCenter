from datetime import timedelta
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from apps.users.models import CustomUser
from apps.clinics.models import Clinic
from apps.pets.models import Pet
from .models import Service, Appointment


class BookingSecurityTests(TestCase):
    def setUp(self):
        self.owner = CustomUser.objects.create_user("owner@example.com", "Pet", "Owner", "strongpass123")
        self.other = CustomUser.objects.create_user("other@example.com", "Other", "Owner", "strongpass123")
        self.clinic = Clinic.objects.create(name="Demo clinic", email="clinic@example.com", address="Street 1", city="Almaty")
        self.pet = Pet.objects.create(owner=self.owner, name="Luna", species="cat")
        self.service = Service.objects.create(clinic=self.clinic, name="Checkup")
        self.slot = (timezone.now() + timedelta(days=2)).replace(second=0, microsecond=0)
        self.client = APIClient()
        self.client.force_authenticate(self.owner)

    def data(self):
        return {"clinic": self.clinic.pk, "pet": str(self.pet.pk), "service": self.service.pk, "starts_at": self.slot.isoformat()}

    def test_conflicting_slot_rejected(self):
        self.assertEqual(self.client.post("/api/appointments/", self.data()).status_code, 201)
        self.assertEqual(self.client.post("/api/appointments/", self.data()).status_code, 400)

    def test_other_owner_cannot_book_my_pet(self):
        self.client.force_authenticate(self.other)
        self.assertEqual(self.client.post("/api/appointments/", self.data()).status_code, 400)

    def test_owner_cannot_view_other_owner_booking(self):
        self.client.post("/api/appointments/", self.data())
        self.client.force_authenticate(self.other)
        self.assertEqual(self.client.get("/api/appointments/").json(), [])
