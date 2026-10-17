from django.db.models import Q
from rest_framework import viewsets, permissions
from rest_framework.exceptions import PermissionDenied
from apps.clinics.access import managed_clinic_ids
from .models import Pet
from .serializers import PetSerializer

class PetViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = PetSerializer

    def get_queryset(self):
        user = self.request.user
        qs = Pet.objects.select_related("owner", "clinic")
        if user.is_superuser:
            return qs
        return qs.filter(Q(owner=user) | Q(clinic_id__in=managed_clinic_ids(user))).distinct()

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)

    def perform_destroy(self, instance):
        if instance.owner_id != self.request.user.pk:
            raise PermissionDenied("Only the pet owner can delete a pet.")
        instance.delete()
