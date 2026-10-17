from datetime import timedelta
from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework import serializers
from apps.clinics.models import Clinic
from apps.clinics.access import has_clinic_role
from apps.clinics.models import ClinicMembership
from .models import Service, Appointment, TransportRequest


class ServiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Service
        fields = ["id", "clinic", "name", "description", "duration_minutes", "price", "is_active"]
        read_only_fields = ["id"]

    def validate_duration_minutes(self, value):
        if value < 1:
            raise serializers.ValidationError("Duration must be at least one minute.")
        return value

    def validate(self, attrs):
        if self.instance and "clinic" in attrs and attrs["clinic"] != self.instance.clinic:
            raise serializers.ValidationError("Cannot move a service to another clinic.")
        if self.instance and "duration_minutes" in attrs:
            new_duration = attrs["duration_minutes"]
            if new_duration != self.instance.duration_minutes and Appointment.objects.filter(
                service=self.instance, status=Appointment.Status.BOOKED,
                starts_at__gt=timezone.now(),
            ).exists():
                raise serializers.ValidationError("Cannot change duration while active bookings exist.")
        return attrs


def ensure_slot_available(clinic, service, start, exclude_id=None):
    if start <= timezone.now():
        raise serializers.ValidationError({"starts_at": "Choose a future slot."})
    if service.duration_minutes < 1:
        raise serializers.ValidationError({"service": "Invalid service duration."})
    end = start + timedelta(minutes=service.duration_minutes)
    existing = Appointment.objects.select_related("service").filter(
        clinic=clinic, status=Appointment.Status.BOOKED, starts_at__lt=end,
    )
    if exclude_id is not None:
        existing = existing.exclude(pk=exclude_id)
    if any(
        row.starts_at + timedelta(minutes=row.service.duration_minutes) > start
        for row in existing
    ):
        raise serializers.ValidationError({"starts_at": "Slot overlaps another appointment."})


class AppointmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Appointment
        fields = ["id", "clinic", "owner", "pet", "service",
                  "starts_at", "status", "created_at"]
        read_only_fields = ["id", "owner", "status", "created_at"]

    def validate(self, attrs):
        clinic = attrs.get("clinic", getattr(self.instance, "clinic", None))
        pet = attrs.get("pet", getattr(self.instance, "pet", None))
        service = attrs.get("service", getattr(self.instance, "service", None))
        start = attrs.get("starts_at", getattr(self.instance, "starts_at", None))
        if not all([clinic, pet, service, start]):
            return attrs
        if not clinic.is_active or pet.owner_id != self.context["request"].user.pk:
            raise serializers.ValidationError("Clinic must be active and pet must belong to you.")
        if not service.is_active or service.clinic_id != clinic.pk:
            raise serializers.ValidationError("Service is not available in this clinic.")
        if start <= timezone.now():
            raise serializers.ValidationError({"starts_at": "Choose a future slot."})
        return attrs

    def create(self, validated_data):
        validated_data["owner"] = self.context["request"].user
        try:
            with transaction.atomic():
                clinic = Clinic.objects.select_for_update().get(pk=validated_data["clinic"].pk)
                ensure_slot_available(clinic, validated_data["service"], validated_data["starts_at"])
                return Appointment.objects.create(**validated_data)
        except IntegrityError:
            raise serializers.ValidationError({"starts_at": "Slot already booked."})


class RescheduleSerializer(serializers.Serializer):
    starts_at = serializers.DateTimeField()

    def validate_starts_at(self, value):
        if value <= timezone.now():
            raise serializers.ValidationError("Choose a future slot.")
        return value


class TransportSerializer(serializers.ModelSerializer):
    class Meta:
        model = TransportRequest
        fields = [
            "id", "appointment", "pickup_address", "contact_phone",
            "handling_notes", "status", "assigned_driver", "updated_at",
        ]
        read_only_fields = ["id", "status", "assigned_driver", "updated_at"]

    def validate_appointment(self, appointment):
        if appointment.owner_id != self.context["request"].user.pk:
            raise serializers.ValidationError("Appointment is not yours.")
        if appointment.status != Appointment.Status.BOOKED:
            raise serializers.ValidationError("Appointment is not active.")
        if hasattr(appointment, "transport"):
            raise serializers.ValidationError("Transport already requested.")
        return appointment

    def create(self, validated_data):
        try:
            with transaction.atomic():
                return TransportRequest.objects.create(**validated_data)
        except IntegrityError:
            raise serializers.ValidationError({"appointment": "Transport request already exists."})
