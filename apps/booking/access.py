from django.db.models import Q

from apps.clinics.access import managed_clinic_ids
from apps.clinics.models import ClinicMembership
from .models import Appointment, TransportRequest


def visible_appointments(user):
    qs = Appointment.objects.select_related("clinic", "pet", "service", "owner")
    if not user or not user.is_authenticated or not user.is_active:
        return qs.none()
    if user.is_superuser:
        return qs
    return qs.filter(Q(owner=user) | Q(clinic_id__in=managed_clinic_ids(user))).distinct()


def visible_transport(user):
    qs = TransportRequest.objects.select_related("appointment", "assigned_driver")
    if not user or not user.is_authenticated or not user.is_active:
        return qs.none()
    if user.is_superuser:
        return qs
    return qs.filter(
        Q(appointment__owner=user)
        | Q(appointment__clinic_id__in=managed_clinic_ids(user))
        | Q(assigned_driver=user,
            appointment__clinic__memberships__user=user,
            appointment__clinic__memberships__role=ClinicMembership.Role.TRANSPORT,
            appointment__clinic__memberships__is_active=True,
            appointment__clinic__is_active=True)
    ).distinct()
