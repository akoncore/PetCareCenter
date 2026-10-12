
from django.contrib import admin

from .models import Pet


@admin.register(Pet)
class PetAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "species",
        "breed",
        "gender",
        "owner",
        "clinic",
        "created_at",
    )

    list_filter = (
        "species",
        "gender",
        "clinic",
        "created_at",
    )

    search_fields = (
        "name",
        "species",
        "breed",
        "owner__email",
        "microchip_number",
    )

    ordering = ("name",)

    readonly_fields = (
        "id",
        "created_at",
        "updated_at",
    )

    list_select_related = (
        "owner",
        "clinic",
    )

    fieldsets = (
        ("Basic information", {
            "fields": (
                "id",
                "name",
                "species",
                "breed",
                "gender",
                "date_of_birth",
                "weight_kg",
                "color",
                "photo",
                "microchip_number",
            ),
        }),
        ("Ownership and clinic", {
            "fields": (
                "owner",
                "clinic",
            ),
        }),
        ("Medical information", {
            "fields": (
                "allergies",
                "notes",
            ),
        }),
        ("Timestamps", {
            "fields": (
                "created_at",
                "updated_at",
            ),
        }),
    )
