"""Core application tests."""

import os
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from integrations.registry import integration_statuses


class CoreViewTests(TestCase):
    def test_health_endpoint_is_public_and_minimal(self):
        response = self.client.get(reverse("healthz"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok", "service": "goreecloud-manager"})

    def test_overview_requires_authentication(self):
        response = self.client.get(reverse("overview"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response.url)

    def test_authenticated_user_can_open_overview(self):
        user = get_user_model().objects.create_user(
            username="admin-test",
            password="strong-test-password",
        )
        self.client.force_login(user)
        response = self.client.get(reverse("overview"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "GoreeCloud Manager")
        self.assertContains(response, "NetBird")


class IntegrationRegistryTests(SimpleTestCase):
    def test_enabled_flag_changes_state_without_returning_token(self):
        with patch.dict(
            os.environ,
            {
                "NETBIRD_ENABLED": "true",
                "NETBIRD_API_TOKEN": "must-never-appear-in-status-output",
            },
            clear=False,
        ):
            statuses = integration_statuses()

        netbird = next(status for status in statuses if status["key"] == "netbird")
        self.assertEqual(netbird["state"], "configured")
        self.assertNotIn("must-never-appear", repr(statuses))

    def test_false_like_or_missing_flags_are_disabled(self):
        with patch.dict(os.environ, {"NETBIRD_ENABLED": "false"}, clear=False):
            statuses = integration_statuses()

        netbird = next(status for status in statuses if status["key"] == "netbird")
        self.assertEqual(netbird["state"], "disabled")
