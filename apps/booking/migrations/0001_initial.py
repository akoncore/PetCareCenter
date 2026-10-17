from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):
    initial = True
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("clinics", "0002_initial"),
        ("pets", "0002_initial"),
    ]
    operations = [
        migrations.CreateModel(name="Service", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("name", models.CharField(max_length=120)),
            ("description", models.TextField(blank=True)),
            ("duration_minutes", models.PositiveSmallIntegerField(default=30)),
            ("price", models.DecimalField(decimal_places=2, default=0, max_digits=10)),
            ("is_active", models.BooleanField(default=True)),
            ("clinic", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="services", to="clinics.clinic")),
        ]),
        migrations.CreateModel(name="Appointment", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("starts_at", models.DateTimeField()),
            ("status", models.CharField(choices=[("booked","Booked"),("cancelled","Cancelled"),("completed","Completed")], default="booked", max_length=12)),
            ("created_at", models.DateTimeField(auto_now_add=True)),
            ("clinic", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="appointments", to="clinics.clinic")),
            ("owner", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="appointments", to=settings.AUTH_USER_MODEL)),
            ("pet", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="appointments", to="pets.pet")),
            ("service", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="appointments", to="booking.service")),
        ]),
        migrations.AddConstraint(model_name="appointment", constraint=models.UniqueConstraint(
            condition=models.Q(status="booked"), fields=("clinic","starts_at"), name="unique_booked_clinic_start")),
        migrations.CreateModel(name="TransportRequest", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("pickup_address", models.CharField(max_length=255)),
            ("contact_phone", models.CharField(max_length=40)),
            ("handling_notes", models.TextField(blank=True)),
            ("status", models.CharField(choices=[("requested","Requested"),("rejected","Rejected"),("confirmed","Confirmed"),("picked_up","Picked up"),("at_clinic","At clinic"),("returning","Returning"),("completed","Completed")], default="requested", max_length=20)),
            ("updated_at", models.DateTimeField(auto_now=True)),
            ("appointment", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="transport", to="booking.appointment")),
            ("assigned_driver", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="transport_jobs", to=settings.AUTH_USER_MODEL)),
        ]),
    ]
