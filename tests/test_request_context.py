"""Request-correlation and request-boundary regression tests for GoreeCloud Manager."""

from __future__ import annotations

from django.db.utils import OperationalError
from django.test import RequestFactory, SimpleTestCase, TestCase
from django.urls import reverse

from core.middleware import RequestContextMiddleware


class RequestContextTests(TestCase):
    def test_request_id_is_server_generated_and_not_caller_controlled(self):
        response = self.client.get(
            reverse("healthz") + "?token=synthetic-query-secret",
            HTTP_X_REQUEST_ID="caller-controlled-request-id",
        )

        self.assertEqual(response.status_code, 200)
        request_id = response["X-Request-ID"]
        self.assertRegex(request_id, r"^[0-9a-f]{32}$")
        self.assertNotEqual(request_id, "caller-controlled-request-id")
        self.assertNotIn("synthetic-query-secret", request_id)

    def test_each_request_receives_a_distinct_request_id(self):
        first = self.client.get(reverse("healthz"))["X-Request-ID"]
        second = self.client.get(reverse("healthz"))["X-Request-ID"]

        self.assertNotEqual(first, second)


class SQLiteContentionBoundaryTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def test_transient_sqlite_lock_returns_sanitized_retryable_503(self):
        def locked_response(request):
            raise OperationalError(
                "database is locked: synthetic /sensitive/database/path must not escape"
            )

        middleware = RequestContextMiddleware(locked_response)

        with self.assertLogs("core.middleware", level="WARNING") as captured:
            response = middleware(self.factory.post("/login/?token=synthetic-secret"))

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response["Retry-After"], "1")
        self.assertEqual(response["Cache-Control"], "no-store")
        self.assertRegex(response["X-Request-ID"], r"^[0-9a-f]{32}$")
        body = response.content.decode()
        self.assertIn("temporarily unavailable", body)
        self.assertNotIn("sensitive", body)
        self.assertNotIn("synthetic-secret", body)
        log_output = "\n".join(captured.output)
        self.assertIn("event=sqlite_contention", log_output)
        self.assertNotIn("sensitive", log_output)
        self.assertNotIn("synthetic-secret", log_output)

    def test_non_lock_operational_error_is_not_hidden(self):
        def broken_response(request):
            raise OperationalError("synthetic unrelated database failure")

        middleware = RequestContextMiddleware(broken_response)

        with self.assertRaisesMessage(
            OperationalError,
            "synthetic unrelated database failure",
        ):
            middleware(self.factory.get("/"))
