
#python modules
from typing import Any
import uuid

from django.db.models import (
    CharField,
    EmailField,
    BooleanField,
    DateTimeField,
    ImageField,
    TextChoices,
    Model,
    UUIDField,  
    ForeignKey,
    CASCADE,  
    PROTECT
    
)
from django.contrib.auth.models import (
    BaseUserManager,
    AbstractBaseUser,
    PermissionsMixin
)
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from django.conf import settings
from django.utils import timezone

class CustomUserManager(BaseUserManager):
    """
    User Manager - handles user creation
    """
    def __obtain_user_instance(
            self,
            email:str,
            first_name:str,
            last_name:str,
            password:str,
            **kwargs:dict[str,Any],
    )-> 'CustomUser':
        """
        Get user instance,
        """
        if not email:
            raise ValidationError(
                message=_("Email field is required"),
                code="email_empty"
            )
        if not first_name and last_name:
            raise ValidationError(
                message=_("Full name is required"),
                code="full_name_empty"
            )
        
        new_user:'CustomUser' = self.model(
            email = self.normalize_email(email),
            first_name = first_name,
            last_name = last_name,
            password = password,
            **kwargs,
        )
        return new_user
    
    def create_user(
        self,
        email:str,
        first_name:str,
        last_name:str,
        password:str,
        **kwargs:dict[str,Any],
    )->'CustomUser':
        """
        Create Cutom User. TODO where is this used?
        """
        new_user: 'CustomUser' = self.__obtain_user_instance(
            email=email,
            first_name = first_name,
            last_name = last_name,
            password=password,
            **kwargs,
        )
        new_user.set_password(password)
        new_user.save(using=self.db)
        return new_user
    
    def create_superuser(
            self,
            email:str,
            first_name:str,
            last_name:str,
            password:str,
            **kwargs:dict[str,Any],
    )-> 'CustomUser':
        """
        Create Superuser
        """
        new_user: 'CustomUser' = self.__obtain_user_instance(
            email=email,
            first_name = first_name,
            last_name = last_name,
            password=password,
            is_active=True,
            is_staff=True,
            is_superuser=True,
            **kwargs,
        )
        new_user.set_password(password)
        new_user.save(using=self.db)
        return new_user


class CustomUser(AbstractBaseUser,PermissionsMixin):
    """
    Model CustomUser
    """
    PREFERRED_LANGUAGES = [
        "en","ru","kz"
    ]
    
    class Role(TextChoices):
        PET_OWNER = "pet_owner", "Pet Owner"
        CLINIC_STAFF = "clinic_staff", "Clinic Staff"
        CLINIC_TRANSPORT = "clinic_transport", "Clinic Transport"
        CLINIC_ADMIN = "clinic_admin", "Clinic Admin"

    role = CharField(
        max_length=30,
        choices=Role.choices,
        default=Role.PET_OWNER,
    )

    email = EmailField(
        unique=True,
        max_length=100,
        db_index=True,
        help_text=_("User email address"),
        verbose_name=_("Email address")
    )
    first_name = CharField(
        max_length=100,
        verbose_name=_("User full name")
    )
    last_name = CharField(
        max_length=150,
        verbose_name=_("User_last_name")
    )
    password = CharField(
        max_length=200,
        verbose_name=_("Password")
    )
    is_active = BooleanField(
        default=True,
        verbose_name=_("Statuc activate")
    )
    is_staff = BooleanField(
        default=False,
        verbose_name="Staff status"
    )
    data_joined = DateTimeField(
        auto_now_add=True
    )
    avatar = ImageField(
        blank=True,
        null=True,
    )
    preferred_language = CharField(
        max_length=10,
        choices=[(lang,lang) for lang in PREFERRED_LANGUAGES],
        default="en",
        verbose_name="Preferred languages",
        help_text="User language"
    )
    timezone = CharField(
        max_length=100,
        default="UTC"
    )

    REQUIRED_FIELDS = ["first_name","last_name"]
    USERNAME_FIELD = "email"
    objects = CustomUserManager()

    class Meta:
        """
        Meta options for CustomUser model
        """
        verbose_name = "Custom User"
        ordering = ["first_name"]
        

class Invitation(Model):

    class Role(TextChoices):
        CLINIC_STAFF = "clinic_staff", "Clinic Staff"
        CLINIC_TRANSPORT = "clinic_transport", "Clinic Transport"
        CLINIC_ADMIN = "clinic_admin", "Clinic Admin"

    id = UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    email = EmailField()

    clinic = ForeignKey(
        "clinics.Clinic",
        on_delete=CASCADE,
        related_name="invitations",
    )

    role = CharField(
        max_length=30,
        choices=Role.choices,
    )

    token_hash = CharField(
        max_length=64,
        unique=True,
    )

    invited_by = ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=PROTECT,
        related_name="sent_invitations",
    )

    expires_at = DateTimeField()

    accepted_at = DateTimeField(
        null=True,
        blank=True,
    )

    created_at = DateTimeField(
        auto_now_add=True,
    )

    @property
    def is_expired(self):
        return timezone.now() >= self.expires_at

    @property
    def is_accepted(self):
        return self.accepted_at is not None
