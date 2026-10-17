from rest_framework import serializers
from apps.clinics.access import has_clinic_role, CLINIC_MANAGERS
from .models import Pet

class PetSerializer(serializers.ModelSerializer):
    class Meta:
        model = Pet
        fields = [
            "id", "owner", "clinic", "name", "species", "breed", "gender",
            "size", "date_of_birth", "weight_kg", "color", "microchip_number",
            "photo", "allergies", "notes", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "owner", "created_at", "updated_at"]

    def validate_clinic(self, clinic):
        if clinic and not clinic.is_active:
            raise serializers.ValidationError("Clinic is inactive.")
        return clinic

    def validate(self, attrs):
        obj = self.instance
        if obj and obj.owner_id != self.context["request"].user.pk:
            if not has_clinic_role(self.context["request"].user, obj.clinic_id, CLINIC_MANAGERS):
                raise serializers.ValidationError("Not allowed to edit this pet.")
            if set(attrs) - {"notes", "allergies", "weight_kg"}:
                raise serializers.ValidationError("Staff can edit only notes, allergies and weight.")
        return attrs
