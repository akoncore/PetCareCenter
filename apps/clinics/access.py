from .models import ClinicMembership

CLINIC_MANAGERS = (ClinicMembership.Role.ADMIN, ClinicMembership.Role.STAFF)

def has_clinic_role(user, clinic_id, roles):
    if not user or not user.is_authenticated or not user.is_active:
        return False
    if user.is_superuser:
        return True
    return ClinicMembership.objects.filter(
        user=user, clinic_id=clinic_id, clinic__is_active=True,
        is_active=True, role__in=roles
    ).exists()

def managed_clinic_ids(user, roles=CLINIC_MANAGERS):
    if not user or not user.is_authenticated or not user.is_active:
        return ClinicMembership.objects.none().values_list("clinic_id", flat=True)
    return ClinicMembership.objects.filter(
        user=user, clinic__is_active=True, is_active=True,
        role__in=roles
    ).values_list("clinic_id", flat=True)
