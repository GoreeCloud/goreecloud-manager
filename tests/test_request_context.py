"""Request-correlation regression tests for GoreeCloud Manager."""

from __future__ import annotations

from django.test import TestCase
from django.urls import reverse


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
