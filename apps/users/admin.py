from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import CustomUser, Invitation
from django.utils.translation import gettext_lazy as _

@admin.register(CustomUser)
class CustomUserAdmin(BaseUserAdmin):
    """
    CustomUser моделі үшін админ панель баптаулары
    """
    list_display = (
        "email",
        "first_name",
        "last_name",
        "is_active",
        "is_staff",
        "date_joined",
    )
    list_filter = ( "is_active", "is_staff", "preferred_language")
    search_fields = ("email", "first_name", "last_name")
    ordering = ("email",)
    
    # Django-ның AbstractBaseUser қолданатындықтан полелерді қайта анықтаймыз
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        (_("Жеке ақпарат"), {"fields": ("first_name", "last_name", "avatar")}),
        (_("Рөлдер мен рұқсаттар"), {
            "fields": ("role", "is_active", "is_staff", "is_superuser", "groups", "user_permissions")
        }),
        (_("Қосымша параметрлер"), {"fields": ("preferred_language", "timezone")}),
        (_("Маңызды уақыттар"), {"fields": ("date_joined", "last_login")}),
    )
    
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": (
                    "email",
                    "first_name",
                    "last_name",
                    "role",
                    "password1",
                    "password2",
                    "is_active",
                    "is_staff",
                ),
            },
        ),
    )
    
    readonly_fields = ("date_joined", "last_login")


@admin.register(Invitation)
class InvitationAdmin(admin.ModelAdmin):
    """
    Клиника қызметкерлерін шақыру (Invitation) моделі үшін баптаулар
    """
    list_display = (
        "email",
        "clinic",
        "role",
        "invited_by",
        "is_expired_status",
        "is_accepted_status",
        "created_at",
    )
    list_filter = ("role", "clinic", "created_at")
    search_fields = ("email", "clinic__name")
    readonly_fields = ("id", "token_hash", "created_at", "invited_by")
    
    @admin.display(description=_("Expired?"), boolean=True)
    def is_expired_status(self, obj):
        return obj.is_expired

    @admin.display(description=_("Accepted?"), boolean=True)
    def is_accepted_status(self, obj):
        return obj.is_accepted