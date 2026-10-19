from django.db import transaction
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .cache import invalidate_catalogue
from .models import Clinic


@receiver(post_save, sender=Clinic)
@receiver(post_delete, sender=Clinic)
def clinic_changed(sender, instance, using, **kwargs):
    transaction.on_commit(invalidate_catalogue, using=using)
