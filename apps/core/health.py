import uuid

from django.conf import settings
from django.core.cache import cache
from django.db import connection
from django.http import JsonResponse
from django.views.decorators.http import require_safe
from redis import Redis


@require_safe
def live(request):
    return JsonResponse({"status": "ok"})


@require_safe
def ready(request):
    checks = {}
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            checks["database"] = cursor.fetchone()[0] == 1
    except Exception:
        checks["database"] = False
    try:
        key = f"health:{uuid.uuid4().hex}"
        cache.set(key, "ok", timeout=5)
        checks["cache"] = cache.get(key) == "ok"
        cache.delete(key)
    except Exception:
        checks["cache"] = False
    try:
        with Redis.from_url(settings.CHANNEL_REDIS_URL, socket_connect_timeout=1,
                            socket_timeout=1) as client:
            checks["channels"] = bool(client.ping())
    except Exception:
        checks["channels"] = False
    healthy = all(checks.values())
    response = JsonResponse({"status": "ok" if healthy else "unavailable", "checks": checks},
                            status=200 if healthy else 503)
    response["Cache-Control"] = "no-store"
    return response
