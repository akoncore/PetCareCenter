
from rest_framework.permissions import BasePermission

from clinics.models import ClinicMembership


def get_clinic_membership(request, view):
    """Get the current user's active membership in the URL clinic."""
    user = request.user

    if not user.is_authenticated:
        return None

    clinic_id = (
        view.kwargs.get("clinic_pk")
        or view.kwargs.get("clinic_id")
    )

    if clinic_id is None:
        return None

    return ClinicMembership.objects.filter(
        user=user,
        clinic_id=clinic_id,
        is_active=True,
        clinic__is_active=True,
    ).first()


class IsOwnerPet(BasePermission):
    """Pet owners can access only their own pets."""

    def has_permission(self, request, view):
        return request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        return obj.owner_id == request.user.id


class IsClinicStaff(BasePermission):
    """Clinic staff can access resources in their clinic."""

    def has_permission(self, request, view):
        membership = get_clinic_membership(request, view)

        return (
            membership is not None
            and membership.role == ClinicMembership.Role.STAFF
        )

    def has_object_permission(self, request, view, obj):
        membership = get_clinic_membership(request, view)

        return (
            membership is not None
            and membership.role == ClinicMembership.Role.STAFF
            and obj.clinic_id == membership.clinic_id
        )


class IsClinicTransport(BasePermission):
    """Transport staff can access only assigned transport jobs."""

    def has_permission(self, request, view):
        membership = get_clinic_membership(request, view)

        return (
            membership is not None
            and membership.role == ClinicMembership.Role.TRANSPORT
        )

    def has_object_permission(self, request, view, obj):
        membership = get_clinic_membership(request, view)

        return (
            membership is not None
            and membership.role == ClinicMembership.Role.TRANSPORT
            and obj.clinic_id == membership.clinic_id
            and obj.transport_assignee_id == request.user.id
        )


class IsClinicAdmin(BasePermission):
    """Clinic admins can manage resources within their clinic."""

    def has_permission(self, request, view):
        membership = get_clinic_membership(request, view)

        return (
            membership is not None
            and membership.role == ClinicMembership.Role.ADMIN
        )

    def has_object_permission(self, request, view, obj):
        membership = get_clinic_membership(request, view)

        return (
            membership is not None
            and membership.role == ClinicMembership.Role.ADMIN
            and obj.clinic_id == membership.clinic_id
        )
