import io
import json
import logging
from unittest.mock import patch

from django.test import TestCase
from redis.exceptions import ConnectionError

from .logging import JsonFormatter, request_id


class HealthAndLoggingTests(TestCase):
    def test_live_and_ready_with_real_database_and_redis(self):
        self.assertEqual(self.client.get("/health/live/").json(), {"status": "ok"})
        response = self.client.get("/health/ready/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["checks"], {"database": True, "cache": True, "channels": True})
        self.assertEqual(response["Cache-Control"], "no-store")

    def test_readiness_returns_503_without_leaking_connection_details(self):
        with patch("apps.core.health.cache.set", side_effect=ConnectionError("redis://private-password@host")):
            response = self.client.get("/health/ready/")
        self.assertEqual(response.status_code, 503)
        self.assertFalse(response.json()["checks"]["cache"])
        self.assertNotIn(b"private-password", response.content)
        self.assertEqual(self.client.get("/health/live/").status_code, 200)

    def test_request_id_correlates_response_and_sanitized_json_log(self):
        stream = io.StringIO()
        handler = logging.StreamHandler(stream)
        handler.setFormatter(JsonFormatter())
        logger = logging.getLogger("petcare.http")
        logger.addHandler(handler)
        try:
            response = self.client.post("/api/auth/login/?token=query-secret", {
                "email": "nobody@example.com", "password": "body-secret",
            }, HTTP_X_REQUEST_ID="untrusted-secret", HTTP_AUTHORIZATION="Token header-secret")
        finally:
            logger.removeHandler(handler)
        records = [json.loads(line) for line in stream.getvalue().splitlines()]
        record = next(row for row in records if row["event"] == "http_request")
        self.assertEqual(record["request_id"], response["X-Request-ID"])
        self.assertEqual(len(record["request_id"]), 32)
        self.assertEqual(record["status"], response.status_code)
        self.assertIsNone(request_id.get())
        for secret in ("query-secret", "body-secret", "header-secret", "untrusted-secret", "nobody@example.com"):
            self.assertNotIn(secret, stream.getvalue())

    def test_exception_log_preserves_stack_locations_without_sensitive_message(self):
        try:
            raise ValueError("password=private-secret")
        except ValueError:
            import sys
            record = logging.LogRecord("django.request", logging.ERROR, __file__, 1,
                                       "private-secret", (), sys.exc_info())
        data = json.loads(JsonFormatter().format(record))
        self.assertEqual(data["error_type"], "ValueError")
        self.assertTrue(data["traceback"])
        self.assertNotIn("private-secret", json.dumps(data))
