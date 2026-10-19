from django.apps import AppConfig


class ClinicsConfig(AppConfig):
    name = 'apps.clinics'

    def ready(self):
        from . import signals  # noqa: F401
