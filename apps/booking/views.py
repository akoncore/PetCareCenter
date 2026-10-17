from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework import permissions, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from apps.clinics.models import ClinicMembership
from apps.clinics.access import CLINIC_MANAGERS, has_clinic_role, managed_clinic_ids
from apps.clinics.models import Clinic
from .models import Service, Appointment, TransportRequest
from .serializers import (
    ServiceSerializer, AppointmentSerializer, RescheduleSerializer,
    TransportSerializer, ensure_slot_available,
)


class ServiceViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = ServiceSerializer
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_queryset(self):
        qs = Service.objects.select_related("clinic")
        user = self.request.user
        if user.is_superuser:
            return qs
        admin_clinics = managed_clinic_ids(user, [ClinicMembership.Role.ADMIN])
        return qs.filter(Q(is_active=True, clinic__is_active=True)
                         | Q(clinic_id__in=admin_clinics)).distinct()

    def perform_create(self, serializer):
        clinic = serializer.validated_data["clinic"]
        if not has_clinic_role(self.request.user, clinic.pk, [ClinicMembership.Role.ADMIN]):
            raise PermissionDenied("Only clinic administrators may add services.")
        if not clinic.is_active:
            raise ValidationError("Clinic is inactive.")
        serializer.save()

    def perform_update(self, serializer):
        obj = self.get_object()
        if not has_clinic_role(self.request.user, obj.clinic_id, [ClinicMembership.Role.ADMIN]):
            raise PermissionDenied("Clinic administrator role required.")
        serializer.save()

    def perform_destroy(self, instance):
        if not has_clinic_role(self.request.user, instance.clinic_id, [ClinicMembership.Role.ADMIN]):
            raise PermissionDenied("Clinic administrator role required.")
        # Keep bookings and historical records intact.
        instance.is_active = False
        instance.save(update_fields=["is_active"])


class AppointmentViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = AppointmentSerializer
    http_method_names = ["get", "post", "head", "options"]

    def get_queryset(self):
        user = self.request.user
        qs = Appointment.objects.select_related("clinic", "pet", "service", "owner")
        if user.is_superuser:
            return qs
        result = qs.filter(Q(owner=user) | Q(clinic_id__in=managed_clinic_ids(user))).distinct()
        requested_status = self.request.query_params.get("status")
        if requested_status in Appointment.Status.values:
            return result.filter(status=requested_status)
        return result

    @action(detail=True, methods=["post"])
    def reschedule(self, request, pk=None):
        serializer = RescheduleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        start = serializer.validated_data["starts_at"]
        with transaction.atomic():
            item = self.get_object()
            # Clinic row serializes slot reservation and reschedule on PostgreSQL.
            Clinic.objects.select_for_update().get(pk=item.clinic_id)
            item = Appointment.objects.select_for_update().get(pk=item.pk)
            if item.owner_id != request.user.pk and not has_clinic_role(
                request.user, item.clinic_id, CLINIC_MANAGERS
            ):
                raise PermissionDenied("Only the owner or clinic staff may reschedule.")
            if item.status != Appointment.Status.BOOKED:
                raise ValidationError("Appointment is not active.")
            if hasattr(item, "transport") and item.transport.status not in [
                TransportRequest.Status.REQUESTED, TransportRequest.Status.REJECTED,
            ]:
                raise ValidationError("Confirmed transport must be rearranged by the clinic.")
            if not item.service.is_active:
                raise ValidationError("Service is unavailable.")
            ensure_slot_available(item.clinic, item.service, start, exclude_id=item.pk)
            item.starts_at = start
            try:
                item.save(update_fields=["starts_at"])
            except IntegrityError:
                raise ValidationError({"starts_at": "Slot already booked."})
        return Response(self.get_serializer(item).data)

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        with transaction.atomic():
            item = self.get_object()
            Clinic.objects.select_for_update().get(pk=item.clinic_id)
            item = Appointment.objects.select_for_update().get(pk=item.pk)
            if item.owner_id != request.user.pk and not has_clinic_role(
                request.user, item.clinic_id, CLINIC_MANAGERS
            ):
                raise PermissionDenied("Owner or clinic staff required.")
            if item.status != Appointment.Status.BOOKED:
                raise ValidationError("Appointment is not active.")
            if hasattr(item, "transport") and item.transport.status not in [
                TransportRequest.Status.REQUESTED, TransportRequest.Status.REJECTED,
            ]:
                raise ValidationError("Confirmed transport must be cancelled by coordination.")
            item.status = Appointment.Status.CANCELLED
            item.save(update_fields=["status"])
        return Response(self.get_serializer(item).data)

    @action(detail=True, methods=["post"])
    def complete(self, request, pk=None):
        item = self.get_object()
        if not has_clinic_role(request.user, item.clinic_id, CLINIC_MANAGERS):
            raise PermissionDenied("Clinic staff required.")
        if item.status != Appointment.Status.BOOKED:
            raise ValidationError("Appointment is not active.")
        item.status = Appointment.Status.COMPLETED
        item.save(update_fields=["status"])
        return Response(self.get_serializer(item).data)


class TransportViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = TransportSerializer
    http_method_names = ["get", "post", "head", "options"]

    def get_queryset(self):
        user = self.request.user
        qs = TransportRequest.objects.select_related("appointment", "assigned_driver")
        if user.is_superuser:
            return qs
        return qs.filter(
            Q(appointment__owner=user)
            | Q(appointment__clinic_id__in=managed_clinic_ids(user))
            | Q(
                assigned_driver=user,
                appointment__clinic__memberships__user=user,
                appointment__clinic__memberships__role=ClinicMembership.Role.TRANSPORT,
                appointment__clinic__memberships__is_active=True,
                appointment__clinic__is_active=True,
            )
        ).distinct()

    @action(detail=True, methods=["post"])
    def advance(self, request, pk=None):
        with transaction.atomic():
            item = self.get_object()
            item = TransportRequest.objects.select_for_update().select_related(
                "appointment__clinic"
            ).get(pk=item.pk)
            clinic = item.appointment.clinic
            admin = has_clinic_role(request.user, clinic.pk, [ClinicMembership.Role.ADMIN])
            staff = has_clinic_role(request.user, clinic.pk, [ClinicMembership.Role.STAFF])
            driver = (item.assigned_driver_id == request.user.pk and
                      has_clinic_role(request.user, clinic.pk, [ClinicMembership.Role.TRANSPORT]))
            allowed = {
                "requested": ("confirmed", "rejected"),
                "confirmed": ("picked_up",),
                "picked_up": ("at_clinic",),
                "at_clinic": ("returning",),
                "returning": ("completed",),
            }
            next_status = request.data.get("status")
            if next_status not in allowed.get(item.status, ()):
                raise ValidationError({"status": "Invalid transport status transition."})
            if item.status == "requested":
                if not (admin or staff):
                    raise PermissionDenied("Clinic staff approval required.")
                if next_status == "confirmed":
                    driver_id = request.data.get("assigned_driver")
                    if not driver_id or not ClinicMembership.objects.filter(
                        user_id=driver_id, user__is_active=True,
                        clinic=clinic, is_active=True,
                        role=ClinicMembership.Role.TRANSPORT,
                    ).exists():
                        raise ValidationError({"assigned_driver": "Choose an active clinic driver."})
                    item.assigned_driver_id = driver_id
            elif not (driver or admin):
                raise PermissionDenied("Assigned driver or clinic administrator required.")
            if item.appointment.status == Appointment.Status.CANCELLED:
                raise ValidationError("Transport cannot proceed for a cancelled appointment.")
            item.status = next_status
            item.save()
        return Response(self.get_serializer(item).data)
