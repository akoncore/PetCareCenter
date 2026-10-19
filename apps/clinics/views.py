from django.db.models import Q
from django.utils import timezone
from rest_framework import permissions, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from apps.booking.models import Appointment, TransportRequest, Service
from .models import Clinic, ClinicMembership
from .serializers import ClinicSerializer, ClinicMembershipSerializer
from .access import has_clinic_role, managed_clinic_ids, CLINIC_MANAGERS
from .cache import public_catalogue_key, read_catalogue, store_catalogue

class ClinicViewSet(viewsets.ModelViewSet):
    serializer_class = ClinicSerializer
    http_method_names = ["get", "post", "patch", "head", "options"]

    def list(self, request, *args, **kwargs):
        # Never share role-dependent responses or future filtered query variants.
        if request.user.is_authenticated or request.query_params:
            return super().list(request, *args, **kwargs)
        key = public_catalogue_key()
        data = read_catalogue(key)
        if data is not None:
            return Response(data)
        response = super().list(request, *args, **kwargs)
        store_catalogue(key, response.data)
        return response

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [permissions.AllowAny()]
        return [permissions.IsAuthenticated()]

    def get_queryset(self):
        qs = Clinic.objects.all()
        user = self.request.user
        if user.is_authenticated and user.is_superuser:
            return qs
        return qs.filter(Q(is_active=True) | Q(pk__in=managed_clinic_ids(user))).distinct()

    def perform_create(self, serializer):
        if not self.request.user.is_superuser:
            raise PermissionDenied("Only system administrators may create clinics.")
        clinic = serializer.save()
        ClinicMembership.objects.get_or_create(
            clinic=clinic, user=self.request.user,
            defaults={"role": ClinicMembership.Role.ADMIN},
        )

    def perform_update(self, serializer):
        if not has_clinic_role(self.request.user, self.get_object().pk, [ClinicMembership.Role.ADMIN]):
            raise PermissionDenied("Clinic administrator role required.")
        serializer.save()

    @action(detail=True, methods=["get"])
    def dashboard(self, request, pk=None):
        clinic = self.get_object()
        if not has_clinic_role(request.user, clinic.pk, CLINIC_MANAGERS):
            raise PermissionDenied("Clinic staff role required.")
        upcoming = Appointment.objects.filter(
            clinic=clinic, status=Appointment.Status.BOOKED,
            starts_at__gte=timezone.now(),
        ).order_by("starts_at")
        return Response({
            "clinic": clinic.pk,
            "active_services": Service.objects.filter(clinic=clinic, is_active=True).count(),
            "upcoming_appointments": upcoming.count(),
            "pending_transport": TransportRequest.objects.filter(
                appointment__clinic=clinic, appointment__status=Appointment.Status.BOOKED,
                status=TransportRequest.Status.REQUESTED,
            ).count(),
            "next_appointments": [
                {"id": a.pk, "pet": str(a.pet_id), "starts_at": a.starts_at.isoformat()}
                for a in upcoming[:10]
            ],
        })

class ClinicMembershipViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = ClinicMembershipSerializer
    http_method_names = ["get", "patch", "head", "options"]

    def get_queryset(self):
        user = self.request.user
        qs = ClinicMembership.objects.select_related("user", "clinic")
        if user.is_superuser:
            return qs
        return qs.filter(clinic_id__in=managed_clinic_ids(user, [ClinicMembership.Role.ADMIN]))

    def partial_update(self, request, *args, **kwargs):
        obj = self.get_object()
        if not has_clinic_role(request.user, obj.clinic_id, [ClinicMembership.Role.ADMIN]):
            raise PermissionDenied("Clinic admin required.")
        serializer = self.get_serializer(obj, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)
