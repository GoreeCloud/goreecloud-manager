"""Regression tests for Manager integration fault isolation."""

from __future__ import annotations

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse


class IntegrationFaultIsolationTests(TestCase):
    def setUp(self):
        user = get_user_model().objects.create_user(
            username="fault-isolation-admin",
            password="strong-test-password",
        )
        self.client.force_login(user)

    @patch(
        "core.views.netbird_snapshot",
        side_effect=RuntimeError("synthetic-secret-value-must-not-escape"),
    )
    def test_unexpected_integration_exception_does_not_break_overview(
        self, mocked_snapshot
    ):
        with self.assertLogs("core.views", level="ERROR") as captured:
            response = self.client.get(reverse("overview"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            "Unexpected NetBird integration failure was contained by Manager.",
        )
        self.assertNotContains(response, "synthetic-secret-value-must-not-escape")
        self.assertTrue(mocked_snapshot.called)
        log_output = "\n".join(captured.output)
        self.assertIn("RuntimeError", log_output)
        self.assertNotIn("synthetic-secret-value-must-not-escape", log_output)

    @patch(
        "core.views.tasks_snapshot",
        side_effect=RuntimeError("synthetic-tasks-token-must-not-escape"),
    )
    def test_unexpected_tasks_exception_is_contained_on_tasks_page(self, mocked_snapshot):
        response = self.client.get(reverse("tasks"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Live task data is not available")
        self.assertContains(
            response,
            "Unexpected GoreeCloud Tasks integration failure was contained by Manager.",
        )
        self.assertNotContains(response, "synthetic-tasks-token-must-not-escape")
        self.assertTrue(mocked_snapshot.called)

    @patch(
        "core.views.tasks_snapshot",
        side_effect=RuntimeError("synthetic-monitoring-secret-must-not-escape"),
    )
    def test_unexpected_tasks_exception_becomes_sanitized_monitoring_failure(
        self, mocked_snapshot
    ):
        response = self.client.get(reverse("tasks-integration-healthz"))

        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            response.json(),
            {
                "status": "unhealthy",
                "service": "goreecloud-manager",
                "integration": "goreecloud-tasks",
                "state": "unavailable",
                "condition": "internal-error",
            },
        )
        self.assertEqual(response["Cache-Control"], "no-store")
        self.assertNotIn(
            "synthetic-monitoring-secret-must-not-escape",
            response.content.decode(),
        )
        self.assertTrue(mocked_snapshot.called)
