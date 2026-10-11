
from django.conf import settings
from django.db.models import (
    Model,
    CharField,
    EmailField,
    TextField,
    JSONField,
    BooleanField,
    DateTimeField,
    ForeignKey,
    CASCADE,
    TextChoices,
    UniqueConstraint
) 
from django.utils.translation import gettext_lazy as _


class Clinic(Model):
    name = CharField(
        max_length=200,
        verbose_name=_("Clinic name"),
    )

    email = EmailField(
        unique=True,
        verbose_name=_("Clinic email"),
    )

    phone = CharField(
        max_length=30,
        blank=True,
        verbose_name=_("Phone number"),
    )

    address = CharField(
        max_length=255,
        verbose_name=_("Address"),
    )

    city = CharField(
        max_length=100,
        verbose_name=_("City"),
    )

    country = CharField(
        max_length=100,
        default="Kazakhstan",
        verbose_name=_("Country"),
    )

    description = TextField(
        blank=True,
        verbose_name=_("Description"),
    )

    opening_hours = JSONField(
        default=dict,
        blank=True,
        verbose_name=_("Opening hours"),
    )

    is_active = BooleanField(
        default=True,
        verbose_name=_("Active status"),
    )

    created_at = DateTimeField(
        auto_now_add=True,
    )

    updated_at = DateTimeField(
        auto_now=True,
    )

    class Meta:
        verbose_name = _("Clinic")
        verbose_name_plural = _("Clinics")
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class ClinicMembership(Model):

    class Role(TextChoices):
        STAFF = "clinic_staff", "Clinic Staff"
        TRANSPORT = "clinic_transport", "Clinic Transport"
        ADMIN = "clinic_admin", "Clinic Admin"

    user = ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=CASCADE,
        related_name="clinic_memberships",
    )

    clinic = ForeignKey(
        "clinics.Clinic",
        on_delete=CASCADE,
        related_name="memberships",
    )

    role = CharField(
        max_length=30,
        choices=Role.choices,
    )

    is_active = BooleanField(default=True)

    class Meta:
        constraints = [
            UniqueConstraint(
                fields=["user", "clinic"],
                name="unique_user_clinic_membership",
            )
        ]

    def __str__(self):
        return f"{self.user.email} - {self.clinic.name}"
