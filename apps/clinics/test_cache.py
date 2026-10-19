from unittest.mock import patch

from django.conf import settings
from django.core.cache import cache
from django.db import transaction
from django.test import TransactionTestCase, override_settings
from redis.exceptions import ConnectionError
from rest_framework.test import APIClient

from apps.users.models import CustomUser
from .cache import invalidate_catalogue, public_catalogue_key, store_catalogue
from .models import Clinic


@override_settings(CACHES={"default": {**settings.CACHES["default"], "KEY_PREFIX": "petcare-tests"}})
class PublicCatalogueCacheTests(TransactionTestCase):
    def setUp(self):
        self.client = APIClient()
        self.clinic = Clinic.objects.create(name="Demo", email="demo@example.com", city="Almaty", address="1 Street")

    def test_second_anonymous_read_uses_cache_without_database_queries(self):
        first = self.client.get("/api/clinics/")
        self.assertEqual(first.status_code, 200)
        with self.assertNumQueries(0):
            second = self.client.get("/api/clinics/")
        self.assertEqual(second.data, first.data)

    def test_save_and_delete_invalidate_cached_catalogue(self):
        self.client.get("/api/clinics/")
        self.clinic.name = "Updated"
        self.clinic.save()
        self.assertEqual(self.client.get("/api/clinics/").data[0]["name"], "Updated")
        self.clinic.delete()
        self.assertEqual(self.client.get("/api/clinics/").data, [])

    def test_authenticated_response_cannot_pollute_public_cache(self):
        self.clinic.is_active = False
        self.clinic.save()
        user = CustomUser.objects.create(email="admin@example.com", is_superuser=True)
        self.client.force_authenticate(user)
        self.assertEqual(len(self.client.get("/api/clinics/").data), 1)
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get("/api/clinics/").data, [])

    def test_inflight_old_response_cannot_repopulate_current_generation(self):
        old_key = public_catalogue_key()
        invalidate_catalogue()
        store_catalogue(old_key, [{"name": "Stale"}])
        self.assertNotEqual(public_catalogue_key(), old_key)
        self.assertEqual(self.client.get("/api/clinics/").data[0]["name"], "Demo")

    def test_rollback_does_not_publish_uncommitted_data(self):
        self.client.get("/api/clinics/")
        key = public_catalogue_key()
        with self.assertRaises(RuntimeError):
            with transaction.atomic():
                self.clinic.name = "Not committed"
                self.clinic.save()
                self.assertIsNone(public_catalogue_key())
                raise RuntimeError("rollback")
        self.assertEqual(public_catalogue_key(), key)
        self.assertEqual(self.client.get("/api/clinics/").data[0]["name"], "Demo")

    def test_cache_failure_falls_back_to_database(self):
        with patch("apps.clinics.cache.cache.get", side_effect=ConnectionError("offline")):
            with self.assertLogs("petcare.cache", level="WARNING"):
                response = self.client.get("/api/clinics/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data[0]["name"], "Demo")

    @override_settings(CLINIC_CACHE_TTL=1)
    def test_cache_has_bounded_ttl(self):
        self.client.get("/api/clinics/")
        key = public_catalogue_key()
        client = cache._cache.get_client(key)
        self.assertGreater(client.ttl(cache.make_key(key)), 0)
        self.assertLessEqual(client.ttl(cache.make_key(key)), 1)
