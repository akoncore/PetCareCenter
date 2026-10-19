import logging
import uuid

from django.conf import settings
from django.core.cache import cache
from django.db import connection
from redis.exceptions import RedisError

logger = logging.getLogger("petcare.cache")
GENERATION_KEY = "clinics:public:generation"


def public_catalogue_key():
    if settings.CLINIC_CACHE_TTL <= 0 or connection.in_atomic_block:
        return None
    try:
        generation = cache.get(GENERATION_KEY)
        if generation is None:
            cache.add(GENERATION_KEY, uuid.uuid4().hex, timeout=None)
            generation = cache.get(GENERATION_KEY)
        return f"clinics:public:{generation}" if generation else None
    except (RedisError, OSError):
        logger.warning("cache_unavailable")
        return None


def read_catalogue(key):
    if key is None:
        return None
    try:
        return cache.get(key)
    except (RedisError, OSError):
        logger.warning("cache_unavailable")
        return None


def store_catalogue(key, data):
    if key is None:
        return
    try:
        cache.set(key, data, timeout=settings.CLINIC_CACHE_TTL)
    except (RedisError, OSError):
        logger.warning("cache_unavailable")


def invalidate_catalogue():
    try:
        # New generation prevents an in-flight old reader from repopulating fresh data.
        cache.set(GENERATION_KEY, uuid.uuid4().hex, timeout=None)
    except (RedisError, OSError):
        logger.warning("cache_invalidation_failed")
