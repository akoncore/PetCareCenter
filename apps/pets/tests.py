from django.test import TestCase
from rest_framework.test import APIClient
from apps.users.models import CustomUser
from apps.clinics.models import Clinic, ClinicMembership
from .models import Pet


class PetApiTests(TestCase):
    def setUp(self):
        self.owner = CustomUser.objects.create_user("owner@example.com", "Pet", "Owner", "StrongPassword444!")
        self.other = CustomUser.objects.create_user("other@example.com", "Other", "User", "StrongPassword444!")
        self.staff = CustomUser.objects.create_user("staff@example.com", "Clinic", "Staff", "StrongPassword444!")
        self.clinic = Clinic.objects.create(
            name="Demo", email="demo@example.com", city="Almaty", address="Example 1"
        )
        ClinicMembership.objects.create(user=self.staff, clinic=self.clinic, role="clinic_staff")
        self.pet = Pet.objects.create(
            owner=self.owner, clinic=self.clinic, name="Luna", species="cat"
        )
        self.client = APIClient()

    def test_owner_can_create_and_staff_can_update_notes_only(self):
        self.client.force_authenticate(self.owner)
        result = self.client.post("/api/pets/", {"name": "Rex", "species": "dog", "size": "large"})
        self.assertEqual(result.status_code, 201, result.data)
        self.assertEqual(result.data["owner"], self.owner.pk)
        self.client.force_authenticate(self.staff)
        self.assertEqual(self.client.patch(
            f"/api/pets/{self.pet.pk}/", {"notes": "Calm handling"}
        ).status_code, 200)
        self.assertEqual(self.client.patch(
            f"/api/pets/{self.pet.pk}/", {"name": "Not allowed"}
        ).status_code, 400)

    def test_other_owner_has_no_access(self):
        self.client.force_authenticate(self.other)
        self.assertEqual(self.client.get(f"/api/pets/{self.pet.pk}/").status_code, 404)
        self.assertEqual(self.client.patch(f"/api/pets/{self.pet.pk}/", {"notes": "hack"}).status_code, 404)
