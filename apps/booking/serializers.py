from datetime import timedelta
from django.db import transaction
from django.utils import timezone
from rest_framework import serializers
from apps.clinics.models import Clinic, ClinicMembership
from apps.pets.models import Pet
from .models import Service, Appointment, TransportRequest


def membership(user, clinic, roles):
    return ClinicMembership.objects.filter(user=user, clinic=clinic, clinic__is_active=True, is_active=True, role__in=roles).exists()


class ServiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Service
        fields = ["id", "clinic", "name", "description", "duration_minutes", "price", "is_active"]
        read_only_fields = ["id"]


class AppointmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Appointment
        fields = ["id", "clinic", "owner", "pet", "service", "starts_at", "status", "created_at"]
        read_only_fields = ["id", "owner", "status", "created_at"]

    def validate(self, attrs):
        clinic = attrs.get("clinic", getattr(self.instance, "clinic", None))
        pet = attrs.get("pet", getattr(self.instance, "pet", None))
        service = attrs.get("service", getattr(self.instance, "service", None))
        starts_at = attrs.get("starts_at", getattr(self.instance, "starts_at", None))
        if not all([clinic, pet, service, starts_at]):
            return attrs
        if not clinic.is_active or pet.owner_id != self.context["request"].user.pk:
            raise serializers.ValidationError("Clinic must be active and pet must belong to you.")
        if service.clinic_id != clinic.pk or not service.is_active:
            raise serializers.ValidationError("Service is unavailable at this clinic.")
        if starts_at <= timezone.now():
            raise serializers.ValidationError("Choose a future slot.")
        return attrs

    def create(self, validated_data):
        validated_data["owner"] = self.context["request"].user
        with transaction.atomic():
            Clinic.objects.select_for_update().get(pk=validated_data["clinic"].pk)
            start = validated_data["starts_at"]
            end = start + timedelta(minutes=validated_data["service"].duration_minutes)
            active = Appointment.objects.select_related("service").filter(
                clinic=validated_data["clinic"], status=Appointment.Status.BOOKED,
                starts_at__lt=end,
            )
            if any(existing.starts_at + timedelta(minutes=existing.service.duration_minutes) > start for existing in active):
                raise serializers.ValidationError({"starts_at": "Slot overlaps an existing appointment."})
            return Appointment.objects.create(**validated_data)


class TransportSerializer(serializers.ModelSerializer):
    class Meta:
        model = TransportRequest
        fields = ["id", "appointment", "pickup_address", "contact_phone", "handling_notes", "status", "assigned_driver", "updated_at"]
        read_only_fields = ["id", "status", "assigned_driver", "updated_at"]

    def validate_appointment(self, appointment):
        if appointment.owner_id != self.context["request"].user.pk:
            raise serializers.ValidationError("Appointment is not yours.")
        if appointment.status != Appointment.Status.BOOKED:
            raise serializers.ValidationError("Appointment is not active.")
        if hasattr(appointment, "transport"):
            raise serializers.ValidationError("Transport already requested.")
        return appointment
