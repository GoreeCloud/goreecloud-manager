"""Authenticated overview rendering tests for Uptime Kuma visibility."""

from datetime import UTC, datetime
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from integrations.uptime_kuma import UptimeKumaMonitor, UptimeKumaSnapshot


class UptimeKumaOverviewTests(TestCase):
    @patch("core.views.uptime_kuma_snapshot")
    def test_authenticated_overview_renders_monitor_metrics(self, mocked_snapshot):
        mocked_snapshot.return_value = UptimeKumaSnapshot(
            state="healthy",
            detail="Live read-only metrics verified for 2 monitor(s).",
            observed_at=datetime(2026, 8, 11, 21, 35, tzinfo=UTC),
            monitors=(
                UptimeKumaMonitor(
                    name="Caddy",
                    monitor_type="http",
                    state="up",
                    response_time_ms=21.0,
                ),
                UptimeKumaMonitor(
                    name="Healthchecks",
                    monitor_type="http",
                    state="up",
                    response_time_ms=34.5,
                ),
            ),
        )

        user = get_user_model().objects.create_user(
            username="uptime-admin-test",
            password="strong-test-password",
        )
        self.client.force_login(user)

        response = self.client.get(reverse("overview"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Uptime Kuma")
        self.assertContains(response, "Read-only Uptime Kuma metrics")
        self.assertContains(response, "Service availability monitoring")
        self.assertContains(response, "Caddy")
        self.assertContains(response, "21 ms")
        self.assertContains(response, "Aug 11, 2026 4:35 PM CDT")
        self.assertContains(response, "Paused-monitor state")
