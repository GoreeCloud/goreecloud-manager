"""View tests for Manager's authenticated Platform live-refresh stream."""

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from integrations.mesh_events import MeshEventStreamStatus


class PlatformEventViewTests(TestCase):
    def _login(self):
        user = get_user_model().objects.create_user(
            username="platform-event-view-test",
            password="strong-test-password",
        )
        self.client.force_login(user)

    def test_platform_event_stream_requires_authentication(self):
        response = self.client.get(reverse("platform-events"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response.url)

    @patch("core.platform_events.mesh_event_stream_status")
    def test_disabled_or_misconfigured_stream_returns_no_content(self, mocked_status):
        self._login()

        mocked_status.return_value = MeshEventStreamStatus("disabled", "disabled")
        response = self.client.get(reverse("platform-events"))
        self.assertEqual(response.status_code, 204)
        self.assertEqual(response["Cache-Control"], "no-store")

        mocked_status.return_value = MeshEventStreamStatus("misconfigured", "secret-free detail")
        response = self.client.get(reverse("platform-events"))
        self.assertEqual(response.status_code, 204)
        self.assertEqual(response.content, b"")

    @patch("core.platform_events.iter_mesh_event_refresh_signals")
    @patch("core.platform_events.mesh_event_stream_status")
    def test_configured_stream_is_no_store_and_same_origin_sanitized(
        self,
        mocked_status,
        mocked_signals,
    ):
        self._login()
        mocked_status.return_value = MeshEventStreamStatus("configured", "configured")
        mocked_signals.return_value = iter(
            ['event: platform-update\ndata: {"type":"mesh.service.upserted.v1"}\n\n']
        )

        response = self.client.get(reverse("platform-events"))

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.streaming)
        self.assertTrue(response["Content-Type"].startswith("text/event-stream"))
        self.assertEqual(response["Cache-Control"], "no-store")
        self.assertEqual(response["X-Accel-Buffering"], "no")
        self.assertEqual(response["X-Content-Type-Options"], "nosniff")
        body = b"".join(response.streaming_content).decode("utf-8")
        self.assertIn("event: platform-update", body)
        self.assertIn("mesh.service.upserted.v1", body)
        self.assertNotIn("Authorization", body)
        self.assertNotIn("Bearer", body)
