from django.test import TestCase
from rest_framework.test import APIClient
from apps.users.models import CustomUser
from .models import Clinic, ClinicMembership


class ClinicApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin = CustomUser.objects.create_user("admin@example.com", "Admin", "One", "StrongPassword444!")
        self.owner = CustomUser.objects.create_user("owner@example.com", "Pet", "Owner", "StrongPassword444!")
        self.clinic = Clinic.objects.create(
            name="Demo", email="demo@clinic.kz", address="1 Street", city="Almaty"
        )
        self.membership = ClinicMembership.objects.create(
            clinic=self.clinic, user=self.admin, role="clinic_admin"
        )

    def test_owner_can_read_clinic_but_cannot_change_it(self):
        self.client.force_authenticate(self.owner)
        self.assertEqual(self.client.get("/api/clinics/").status_code, 200)
        self.assertEqual(self.client.patch(
            f"/api/clinics/{self.clinic.pk}/", {"name": "Hijacked"}
        ).status_code, 403)

    def test_admin_can_manage_own_clinic_and_dashboard(self):
        self.client.force_authenticate(self.admin)
        self.assertEqual(self.client.patch(
            f"/api/clinics/{self.clinic.pk}/", {"name": "Updated"}
        ).status_code, 200)
        response = self.client.get(f"/api/clinics/{self.clinic.pk}/dashboard/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("pending_transport", response.data)

    def test_last_admin_cannot_be_deactivated(self):
        self.client.force_authenticate(self.admin)
        response = self.client.patch(
            f"/api/memberships/{self.membership.pk}/", {"is_active": False}
        )
        self.assertEqual(response.status_code, 400)
