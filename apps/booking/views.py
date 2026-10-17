from django.db import transaction
from rest_framework import viewsets, mixins, permissions, serializers, status
from rest_framework.decorators import action
from rest_framework.response import Response
from apps.clinics.models import ClinicMembership
from .models import Service, Appointment, TransportRequest
from .serializers import ServiceSerializer, AppointmentSerializer, TransportSerializer, membership


class ServiceViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = ServiceSerializer

    def get_queryset(self):
        return Service.objects.filter(is_active=True, clinic__is_active=True)


class AppointmentViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin,
                         mixins.CreateModelMixin, viewsets.GenericViewSet):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = AppointmentSerializer

    def get_queryset(self):
        user = self.request.user
        clinic_ids = ClinicMembership.objects.filter(
            user=user, is_active=True, clinic__is_active=True,
            role__in=[ClinicMembership.Role.ADMIN, ClinicMembership.Role.STAFF],
        ).values_list("clinic_id", flat=True)
        from django.db.models import Q
        return Appointment.objects.filter(Q(owner=user) | Q(clinic_id__in=clinic_ids)).distinct()

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        item = self.get_object()
        if item.owner_id != request.user.pk:
            return Response({"detail": "Only the owner may cancel."}, status=403)
        if item.status != Appointment.Status.BOOKED:
            return Response({"detail": "Not an active booking."}, status=400)
        if hasattr(item, "transport") and item.transport.status not in [
            TransportRequest.Status.REQUESTED, TransportRequest.Status.REJECTED
        ]:
            return Response({"detail": "Contact the clinic: transport is underway or confirmed."}, status=400)
        item.status = Appointment.Status.CANCELLED
        item.save(update_fields=["status"])
        return Response(self.get_serializer(item).data)


class TransportViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin,
                       mixins.CreateModelMixin, viewsets.GenericViewSet):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = TransportSerializer

    def get_queryset(self):
        user = self.request.user
        clinic_ids = ClinicMembership.objects.filter(
            user=user, is_active=True, clinic__is_active=True,
            role__in=[ClinicMembership.Role.ADMIN, ClinicMembership.Role.STAFF],
        ).values_list("clinic_id", flat=True)
        from django.db.models import Q
        return TransportRequest.objects.filter(
            Q(appointment__owner=user) | Q(appointment__clinic_id__in=clinic_ids) | Q(
                assigned_driver=user,
                appointment__clinic__memberships__user=user,
                appointment__clinic__memberships__role=ClinicMembership.Role.TRANSPORT,
                appointment__clinic__memberships__is_active=True,
            )
        ).distinct()

    @action(detail=True, methods=["post"])
    def advance(self, request, pk=None):
        with transaction.atomic():
            obj = self.get_queryset().select_for_update().get(pk=self.get_object().pk)
            clinic = obj.appointment.clinic
            user = request.user
            admin = membership(user, clinic, [ClinicMembership.Role.ADMIN])
            staff = membership(user, clinic, [ClinicMembership.Role.STAFF])
            driver = obj.assigned_driver_id == user.pk and membership(user, clinic, [ClinicMembership.Role.TRANSPORT])
            next_states = {
                "requested": ["confirmed", "rejected"],
                "confirmed": ["picked_up"],
                "picked_up": ["at_clinic"],
                "at_clinic": ["returning"],
                "returning": ["completed"],
            }
            new_status = request.data.get("status")
            if new_status not in next_states.get(obj.status, []):
                return Response({"detail": "Invalid status transition."}, status=400)
            if obj.status == "requested":
                if not (admin or staff):
                    return Response({"detail": "Clinic staff approval required."}, status=403)
                if new_status == "confirmed":
                    driver_id = request.data.get("assigned_driver")
                    if not driver_id or not ClinicMembership.objects.filter(
                        user_id=driver_id, clinic=clinic, is_active=True,
                        role=ClinicMembership.Role.TRANSPORT,
                    ).exists():
                        return Response({"detail": "Choose an active clinic transport member."}, status=400)
                    obj.assigned_driver_id = driver_id
            elif not (driver or admin):
                return Response({"detail": "Assigned driver or clinic admin required."}, status=403)
            obj.status = new_status
            obj.save()
        return Response(self.get_serializer(obj).data)
