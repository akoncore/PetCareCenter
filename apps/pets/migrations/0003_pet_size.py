from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [("pets", "0002_initial")]
    operations = [
        migrations.AddField(
            model_name="pet", name="size",
            field=models.CharField(
                max_length=10,
                choices=[
                    ("unknown", "Unknown"), ("small", "Small"),
                    ("medium", "Medium"), ("large", "Large"),
                ], default="unknown",
            ),
        ),
    ]
