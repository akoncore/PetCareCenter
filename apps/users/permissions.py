
from rest_framework.permissions import BasePermission


class IsOwnerPet(BasePermission):
    """Pet Owner can access only their own pets."""

    def has_permission(self, request, view):
        user = request.user

        return (
            user.is_authenticated
            and user.role == "pet_owner"
        )

    def has_object_permission(self, request, view, obj):
        return obj.owner_id == request.user.id


class IsClinicStaff(BasePermission):
    """Clinic staff can access pets belonging to their clinic."""

    def has_permission(self, request, view):
        user = request.user

        return (
            user.is_authenticated
            and user.role == "clinic_staff"
        )

    def has_object_permission(self, request, view, obj):
        return obj.clinic_id == request.user.clinic_id


class IsClinicTransport(BasePermission):
    """Transport staff access only assigned transport jobs."""

    def has_permission(self, request, view):
        user = request.user

        return (
            user.is_authenticated
            and user.role == "clinic_transport"
        )

    def has_object_permission(self, request, view, obj):
        return obj.transport_assignee_id == request.user.id


class IsClinicAdmin(BasePermission):
    """Clinic admin manages resources within their clinic."""

    def has_permission(self, request, view):
        user = request.user

        return (
            user.is_authenticated
            and user.role == "clinic_admin"
        )

    def has_object_permission(self, request, view, obj):
        return obj.clinic_id == request.user.clinic_id
