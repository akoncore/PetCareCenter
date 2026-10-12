
import uuid

from django.conf import settings
from django.db import models


class Pet(models.Model):

    class Gender(models.TextChoices):
        MALE = "male", "Male"
        FEMALE = "female", "Female"
        UNKNOWN = "unknown", "Unknown"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="pets",
    )

    clinic = models.ForeignKey(
        "clinics.Clinic",
        on_delete=models.PROTECT,
        related_name="pets",
        null=True,
        blank=True,
    )

    name = models.CharField(max_length=100)

    species = models.CharField(
        max_length=50,
        help_text="Dog, cat, bird, etc.",
    )

    breed = models.CharField(
        max_length=100,
        blank=True,
    )

    gender = models.CharField(
        max_length=10,
        choices=Gender.choices,
        default=Gender.UNKNOWN,
    )

    date_of_birth = models.DateField(
        null=True,
        blank=True,
    )

    weight_kg = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        null=True,
        blank=True,
    )

    color = models.CharField(
        max_length=50,
        blank=True,
    )

    microchip_number = models.CharField(
        max_length=50,
        unique=True,
        null=True,
        blank=True,
    )

    photo = models.ImageField(
        upload_to="pets/",
        null=True,
        blank=True,
    )

    allergies = models.TextField(blank=True)

    notes = models.TextField(blank=True)

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = ["name"]
        verbose_name = "Pet"
        verbose_name_plural = "Pets"

    def __str__(self) -> str:
        return f"{self.name} ({self.species})"
