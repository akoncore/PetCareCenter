from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone


class Service(models.Model):
    clinic = models.ForeignKey("clinics.Clinic", on_delete=models.CASCADE, related_name="services")
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    duration_minutes = models.PositiveSmallIntegerField(default=30)
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class Appointment(models.Model):
    class Status(models.TextChoices):
        BOOKED = "booked", "Booked"
        CANCELLED = "cancelled", "Cancelled"
        COMPLETED = "completed", "Completed"

    clinic = models.ForeignKey("clinics.Clinic", on_delete=models.PROTECT, related_name="appointments")
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="appointments")
    pet = models.ForeignKey("pets.Pet", on_delete=models.PROTECT, related_name="appointments")
    service = models.ForeignKey(Service, on_delete=models.PROTECT, related_name="appointments")
    starts_at = models.DateTimeField()
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.BOOKED)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["clinic", "starts_at"], condition=Q(status="booked"),
                                    name="unique_booked_clinic_start"),
        ]

    def __str__(self):
        return f"{self.pet} - {self.starts_at}"


class TransportRequest(models.Model):
    class Status(models.TextChoices):
        REQUESTED = "requested", "Requested"
        REJECTED = "rejected", "Rejected"
        CONFIRMED = "confirmed", "Confirmed"
        PICKED_UP = "picked_up", "Picked up"
        AT_CLINIC = "at_clinic", "At clinic"
        RETURNING = "returning", "Returning"
        COMPLETED = "completed", "Completed"

    appointment = models.OneToOneField(Appointment, on_delete=models.CASCADE, related_name="transport")
    pickup_address = models.CharField(max_length=255)
    contact_phone = models.CharField(max_length=40)
    handling_notes = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.REQUESTED)
    assigned_driver = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="transport_jobs")
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Transport for appointment {self.appointment_id}"
