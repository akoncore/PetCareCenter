import hashlib
import secrets
from datetime import timedelta
from django.contrib.auth import authenticate
from django.db import transaction
from django.utils import timezone
from rest_framework import generics, permissions, status, viewsets
from rest_framework.authtoken.models import Token
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView
from apps.clinics.access import has_clinic_role, managed_clinic_ids
from apps.clinics.models import ClinicMembership
from .models import Invitation
from .serializers import UserSerializer, RegistrationSerializer, InvitationSerializer


class RegisterView(generics.CreateAPIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = RegistrationSerializer


class LoginView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        email = request.data.get("email", "")
        password = request.data.get("password", "")
        if not isinstance(email, str) or not isinstance(password, str):
            raise ValidationError("Email and password are required.")
        user = authenticate(request, username=email.strip().lower(), password=password)
        if user is None or not user.is_active:
            return Response({"detail": "Invalid login credentials."}, status=400)
        token, _ = Token.objects.get_or_create(user=user)
        return Response({"token": token.key, "user": UserSerializer(user).data})


class LogoutView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        Token.objects.filter(user=request.user).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class MeView(generics.RetrieveUpdateAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = UserSerializer
    http_method_names = ["get", "patch", "head", "options"]

    def get_object(self):
        return self.request.user


class InvitationViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = InvitationSerializer
    http_method_names = ["get", "post", "head", "options"]

    def get_queryset(self):
        user = self.request.user
        qs = Invitation.objects.select_related("clinic", "invited_by")
        if user.is_superuser:
            return qs
        return qs.filter(clinic_id__in=managed_clinic_ids(user, [ClinicMembership.Role.ADMIN]))

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        clinic = serializer.validated_data["clinic"]
        if not has_clinic_role(request.user, clinic.pk, [ClinicMembership.Role.ADMIN]):
            raise PermissionDenied("Only clinic administrators can invite staff.")
        raw_token = secrets.token_urlsafe(32)
        invitation = Invitation.objects.create(
            clinic=clinic, email=serializer.validated_data["email"],
            role=serializer.validated_data["role"],
            invited_by=request.user,
            token_hash=hashlib.sha256(raw_token.encode()).hexdigest(),
            expires_at=timezone.now() + timedelta(days=7),
        )
        result = self.get_serializer(invitation).data
        # MVP: provide the one-time invite token to the administrator (no email service).
        result["invitation_token"] = raw_token
        return Response(result, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["post"])
    def accept(self, request):
        token = request.data.get("token")
        if not isinstance(token, str) or not token:
            raise ValidationError({"token": "Invitation token is required."})
        digest = hashlib.sha256(token.encode()).hexdigest()
        with transaction.atomic():
            invitation = Invitation.objects.select_for_update().filter(token_hash=digest).first()
            if invitation is None or invitation.is_expired or invitation.is_accepted:
                raise ValidationError({"token": "Invitation is invalid or expired."})
            if invitation.email.lower() != request.user.email.lower():
                raise PermissionDenied("Invitation belongs to another user.")
            if not invitation.clinic.is_active:
                raise ValidationError("Clinic is inactive.")
            ClinicMembership.objects.update_or_create(
                user=request.user, clinic=invitation.clinic,
                defaults={"role": invitation.role, "is_active": True},
            )
            invitation.accepted_at = timezone.now()
            invitation.save(update_fields=["accepted_at"])
        return Response({"clinic": invitation.clinic_id, "role": invitation.role})
