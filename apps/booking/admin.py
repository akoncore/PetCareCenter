from django.contrib import admin
from .models import Service, Appointment, TransportRequest

@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ("name", "clinic", "duration_minutes", "price", "is_active")

@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = ("pet", "clinic", "service", "starts_at", "status")
    list_filter = ("status", "clinic")

@admin.register(TransportRequest)
class TransportRequestAdmin(admin.ModelAdmin):
    list_display = ("appointment", "status", "assigned_driver", "updated_at")
