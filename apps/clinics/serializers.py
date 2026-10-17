from rest_framework import serializers
from .models import Clinic, ClinicMembership

class ClinicSerializer(serializers.ModelSerializer):
    class Meta:
        model = Clinic
        fields = ["id", "name", "email", "phone", "address", "city", "country",
                  "description", "opening_hours", "is_active", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]

class ClinicMembershipSerializer(serializers.ModelSerializer):
    user_email = serializers.EmailField(source="user.email", read_only=True)
    class Meta:
        model = ClinicMembership
        fields = ["id", "clinic", "user", "user_email", "role", "is_active"]
        read_only_fields = ["id", "clinic", "user", "user_email"]

    def validate(self, attrs):
        obj = self.instance
        if obj and obj.role == ClinicMembership.Role.ADMIN and obj.is_active:
            will_be_admin = attrs.get("role", obj.role) == ClinicMembership.Role.ADMIN
            will_be_active = attrs.get("is_active", obj.is_active)
            if not (will_be_admin and will_be_active):
                another = ClinicMembership.objects.filter(
                    clinic=obj.clinic, role=ClinicMembership.Role.ADMIN,
                    is_active=True,
                ).exclude(pk=obj.pk).exists()
                if not another:
                    raise serializers.ValidationError("Cannot remove the last clinic administrator.")
        return attrs
