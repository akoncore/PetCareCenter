import asyncio
import logging

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Appointment, TransportRequest

logger = logging.getLogger("petcare.realtime")


def publish_change(resource, resource_id):
    try:
        async def send():
            await asyncio.wait_for(get_channel_layer().group_send(
                f"{resource}.{resource_id}",
                {"type": "resource.changed", "resource": resource, "id": resource_id},
            ), timeout=2)

        async_to_sync(send)()
    except Exception:
        # Database commit remains successful when Redis is down. Events are best effort.
        logger.exception("notification_failed", extra={"resource": resource, "resource_id": resource_id})


@receiver(post_save, sender=Appointment)
@receiver(post_save, sender=TransportRequest)
def resource_saved(sender, instance, using, raw=False, **kwargs):
    if raw:
        return
    resource = "appointment" if sender is Appointment else "transport"
    resource_id = instance.pk
    transaction.on_commit(lambda: publish_change(resource, resource_id), using=using)
