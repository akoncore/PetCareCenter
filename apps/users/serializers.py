from django.contrib.auth import get_user_model, password_validation
from rest_framework import serializers
from .models import Invitation

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "email", "first_name", "last_name", "avatar",
                  "preferred_language", "timezone", "date_joined"]
        read_only_fields = ["id", "email", "date_joined"]


class RegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, style={"input_type": "password"}, min_length=8)

    class Meta:
        model = User
        fields = ["id", "email", "first_name", "last_name", "password"]
        read_only_fields = ["id"]

    def validate_email(self, value):
        value = value.strip().lower()
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("Email already registered.")
        return value

    def validate_password(self, value):
        password_validation.validate_password(value)
        return value

    def create(self, validated_data):
        return User.objects.create_user(**validated_data)


class InvitationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Invitation
        fields = ["id", "email", "clinic", "role", "invited_by",
                  "expires_at", "accepted_at", "created_at"]
        read_only_fields = ["id", "invited_by", "expires_at", "accepted_at", "created_at"]

    def validate_email(self, value):
        return value.strip().lower()
