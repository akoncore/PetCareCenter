from django.contrib import admin
from .models import Clinic, ClinicMembership


class ClinicMembershipInline(admin.TabularInline):
    """Клиникаға тіркелген қызметкерлерді Clinic бетінің ішінде көрсету үшін"""
    model = ClinicMembership
    extra = 1
    autocomplete_fields = ["user"]


@admin.register(Clinic)
class ClinicAdmin(admin.ModelAdmin):
    list_display = ("name", "city", "country", "phone", "email", "is_active", "created_at")
    list_filter = ("is_active", "city", "country")
    search_fields = ("name", "email", "city", "address")
    readonly_fields = ("created_at", "updated_at")
    inlines = [ClinicMembershipInline]
    
    fieldsets = (
        ("Негізгі ақпарат", {
            "fields": ("name", "description", "is_active")
        }),
        ("Байланыс деректері", {
            "fields": ("email", "phone", "address", "city", "country")
        }),
        ("Жұмыс кестесі", {
            "fields": ("opening_hours",)
        }),
        ("Уақыт белгілері", {
            "fields": ("created_at", "updated_at"),
            "classes": ("collapse",)
        }),
    )


@admin.register(ClinicMembership)
class ClinicMembershipAdmin(admin.ModelAdmin):
    list_display = ("user", "clinic", "role", "is_active")
    list_filter = ("role", "is_active", "clinic")
    search_fields = ("user__email", "clinic__name")
    list_editable = ("role", "is_active")