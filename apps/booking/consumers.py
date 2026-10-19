import asyncio
import json
import logging

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.conf import settings
from rest_framework.authtoken.models import Token

from .access import visible_appointments, visible_transport

logger = logging.getLogger("petcare.realtime")


class BookingConsumer(AsyncJsonWebsocketConsumer):
    """Read-only change notifications; fetch current state using the REST API."""

    async def connect(self):
        self.token = None
        self.joined = False
        self.closing = False
        self.resource = self.scope["url_route"]["kwargs"]["resource"]
        self.resource_id = self.scope["url_route"]["kwargs"]["pk"]
        self.group = f"{self.resource}.{self.resource_id}"
        await self.accept()
        self.auth_timer = asyncio.create_task(self.require_authentication())

    async def require_authentication(self):
        await asyncio.sleep(settings.WEBSOCKET_AUTH_TIMEOUT)
        if not self.joined:
            await self.close(code=4401)

    async def receive(self, text_data=None, bytes_data=None, **kwargs):
        if text_data is None or len(text_data) > 2048:
            await self.close(code=4400)
            return
        try:
            content = json.loads(text_data)
        except (ValueError, TypeError):
            await self.close(code=4400)
            return
        if not isinstance(content, dict):
            await self.close(code=4400)
            return
        await self.receive_json(content)

    async def receive_json(self, content, **kwargs):
        if self.closing:
            return
        if not self.joined:
            token = content.get("token")
            if content.get("type") != "authenticate" or not isinstance(token, str) or len(token) != 40:
                await self.close(code=4401)
                return
            self.token = token
            denial = await self.access_denial()
            if denial:
                await self.close(code=denial)
                return
            try:
                await self.channel_layer.group_add(self.group, self.channel_name)
            except Exception:
                logger.exception("subscription_failed")
                await self.close(code=1013)
                return
            self.joined = True
            if self.closing:
                return
            self.auth_timer.cancel()
            await self.send_json({"type": "ready", "resource": self.resource, "id": self.resource_id})
        elif content.get("type") == "ping":
            denial = await self.access_denial()
            if denial:
                await self.close(code=denial)
            else:
                await self.send_json({"type": "pong"})
        else:
            await self.close(code=4400)

    @database_sync_to_async
    def access_denial(self):
        token = Token.objects.select_related("user").filter(key=self.token, user__is_active=True).first()
        if token is None:
            return 4401
        queryset = visible_appointments(token.user) if self.resource == "appointment" else visible_transport(token.user)
        return None if queryset.filter(pk=self.resource_id).exists() else 4403

    async def resource_changed(self, event):
        if not self.joined or self.closing:
            return
        # Recheck token and current permissions before *every* notification.
        denial = await self.access_denial()
        if denial:
            await self.close(code=denial)
            return
        await self.send_json({"type": "changed", "resource": self.resource, "id": self.resource_id})

    async def close(self, code=None, reason=None):
        self.closing = True
        await super().close(code=code, reason=reason)

    async def disconnect(self, code):
        if hasattr(self, "auth_timer"):
            self.auth_timer.cancel()
            try:
                await self.auth_timer
            except asyncio.CancelledError:
                pass
        if self.joined:
            try:
                await self.channel_layer.group_discard(self.group, self.channel_name)
            except Exception:
                logger.exception("unsubscribe_failed")
