from django.test import TestCase
from rest_framework.test import APIClient
from apps.clinics.models import Clinic, ClinicMembership
from .models import CustomUser, Invitation


class UserApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin = CustomUser.objects.create_user("admin@demo.kz", "Clinic", "Admin", "StrongPassword444!")
        self.clinic = Clinic.objects.create(
            name="Demo", email="clinic@demo.kz", address="Example street", city="Almaty"
        )
        ClinicMembership.objects.create(
            user=self.admin, clinic=self.clinic, role=ClinicMembership.Role.ADMIN
        )

    def test_registration_and_login(self):
        response = self.client.post("/api/auth/register/", {
            "email": "Owner@Example.com", "first_name": "Pet", "last_name": "Owner",
            "password": "StrongPassword444!",
        })
        self.assertEqual(response.status_code, 201, response.data)
        self.assertNotIn("password", response.data)
        login = self.client.post("/api/auth/login/", {
            "email": "OWNER@EXAMPLE.COM", "password": "StrongPassword444!",
        })
        self.assertEqual(login.status_code, 200, login.data)
        self.assertIn("token", login.data)

    def test_invitations_require_clinic_admin_and_email_match(self):
        owner = CustomUser.objects.create_user("owner@example.com", "Pet", "Owner", "StrongPassword444!")
        self.client.force_authenticate(owner)
        denied = self.client.post("/api/invitations/", {
            "clinic": self.clinic.pk, "email": owner.email, "role": "clinic_staff",
        })
        self.assertEqual(denied.status_code, 403)
        self.client.force_authenticate(self.admin)
        invited = self.client.post("/api/invitations/", {
            "clinic": self.clinic.pk, "email": "owner@example.com", "role": "clinic_staff",
        })
        self.assertEqual(invited.status_code, 201, invited.data)
        token = invited.data["invitation_token"]
        self.client.force_authenticate(owner)
        accepted = self.client.post("/api/invitations/accept/", {"token": token})
        self.assertEqual(accepted.status_code, 200, accepted.data)
        self.assertTrue(ClinicMembership.objects.filter(
            user=owner, clinic=self.clinic, role="clinic_staff", is_active=True
        ).exists())
        self.assertEqual(self.client.post("/api/invitations/accept/", {"token": token}).status_code, 400)

    def test_cannot_accept_invitation_for_other_email(self):
        user = CustomUser.objects.create_user("wrong@example.com", "Wrong", "User", "StrongPassword444!")
        self.client.force_authenticate(self.admin)
        result = self.client.post("/api/invitations/", {
            "clinic": self.clinic.pk, "email": "correct@example.com", "role": "clinic_transport",
        })
        self.client.force_authenticate(user)
        self.assertEqual(
            self.client.post("/api/invitations/accept/", {"token": result.data["invitation_token"]}).status_code,
            403,
        )
