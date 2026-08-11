"""Tests for the read-only Healthchecks integration."""

import os
from unittest.mock import Mock, patch

import httpx
from django.test import SimpleTestCase

from integrations.healthchecks import healthchecks_snapshot


class HealthchecksAdapterTests(SimpleTestCase):
    def _response(self, *, status_code=200, payload=None):
        response = Mock()
        response.status_code = status_code
        response.json.return_value = {"checks": []} if payload is None else payload
        response.raise_for_status.return_value = None
        return response

    @patch("integrations.healthchecks.httpx.get")
    def test_success_normalizes_check_data_and_counts(self, mocked_get):
        mocked_get.return_value = self._response(
            payload={
                "checks": [
                    {
                        "name": "GoreeCloud Healthchecks Validation",
                        "slug": "goreecloud-healthchecks-validation",
                        "tags": "goreecloud validation vps",
                        "status": "up",
                        "started": False,
                        "last_ping": "2026-08-11T10:00:00Z",
                        "next_ping": "2026-08-11T10:05:00Z",
                        "unique_key": "validation-key",
                        "timeout": 300,
                        "grace": 300,
                    },
                    {
                        "name": "GoreeCloud Kopia Backup",
                        "slug": "goreecloud-kopia-backup",
                        "tags": "goreecloud backup kopia vps",
                        "status": "up",
                        "started": False,
                        "last_ping": "2026-08-11T06:00:00Z",
                        "next_ping": "2026-08-12T06:00:00Z",
                        "unique_key": "kopia-key",
                        "timeout": 86400,
                        "grace": 43200,
                    },
                ]
            }
        )

        with patch.dict(
            os.environ,
            {
                "HEALTHCHECKS_ENABLED": "true",
                "HEALTHCHECKS_API_URL": "https://healthchecks.example.test/api/v3",
                "HEALTHCHECKS_API_KEY": "test-read-only-key",
            },
            clear=False,
        ):
            snapshot = healthchecks_snapshot()

        self.assertEqual(snapshot.state, "healthy")
        self.assertEqual(snapshot.total, 2)
        self.assertEqual(snapshot.up, 2)
        self.assertEqual(snapshot.attention, 0)
        self.assertIsNotNone(snapshot.kopia_check)
        self.assertEqual(snapshot.kopia_check.slug, "goreecloud-kopia-backup")
        self.assertEqual(snapshot.kopia_check.schedule_label, "1 day")
        self.assertEqual(snapshot.kopia_check.grace_label, "12 hours")
        _, kwargs = mocked_get.call_args
        self.assertEqual(kwargs["headers"]["X-Api-Key"], "test-read-only-key")
        self.assertNotIn("test-read-only-key", snapshot.detail)

    @patch("integrations.healthchecks.httpx.get")
    def test_down_or_grace_check_degrades_summary(self, mocked_get):
        mocked_get.return_value = self._response(
            payload={
                "checks": [
                    {
                        "name": "Down check",
                        "slug": "down-check",
                        "tags": "goreecloud",
                        "status": "down",
                        "grace": 300,
                        "timeout": 300,
                    },
                    {
                        "name": "Grace check",
                        "slug": "grace-check",
                        "tags": "goreecloud",
                        "status": "grace",
                        "grace": 300,
                        "timeout": 300,
                    },
                ]
            }
        )
        with patch.dict(
            os.environ,
            {
                "HEALTHCHECKS_ENABLED": "true",
                "HEALTHCHECKS_API_URL": "https://healthchecks.example.test/api/v3",
                "HEALTHCHECKS_API_KEY": "secret-value",
            },
            clear=False,
        ):
            snapshot = healthchecks_snapshot()

        self.assertEqual(snapshot.state, "degraded")
        self.assertEqual(snapshot.attention, 2)
        self.assertEqual(snapshot.down, 1)
        self.assertEqual(snapshot.grace, 1)
        self.assertIn("2 require attention", snapshot.detail)

    @patch("integrations.healthchecks.httpx.get")
    def test_timeout_degrades_to_unavailable(self, mocked_get):
        mocked_get.side_effect = httpx.TimeoutException("slow")
        with patch.dict(
            os.environ,
            {
                "HEALTHCHECKS_ENABLED": "true",
                "HEALTHCHECKS_API_URL": "https://healthchecks.example.test/api/v3",
                "HEALTHCHECKS_API_KEY": "secret-value",
            },
            clear=False,
        ):
            snapshot = healthchecks_snapshot()

        self.assertEqual(snapshot.state, "unavailable")
        self.assertIn("timeout", snapshot.detail)
        self.assertNotIn("secret-value", snapshot.detail)

    @patch("integrations.healthchecks.httpx.get")
    def test_authentication_failure_is_sanitized(self, mocked_get):
        mocked_get.return_value = self._response(status_code=401)
        with patch.dict(
            os.environ,
            {
                "HEALTHCHECKS_ENABLED": "true",
                "HEALTHCHECKS_API_URL": "https://healthchecks.example.test/api/v3",
                "HEALTHCHECKS_API_KEY": "secret-value",
            },
            clear=False,
        ):
            snapshot = healthchecks_snapshot()

        self.assertEqual(snapshot.state, "unavailable")
        self.assertIn("credential", snapshot.detail)
        self.assertNotIn("secret-value", snapshot.detail)

    @patch("integrations.healthchecks.httpx.get")
    def test_malformed_response_is_unavailable(self, mocked_get):
        mocked_get.return_value = self._response(payload={"unexpected": []})
        with patch.dict(
            os.environ,
            {
                "HEALTHCHECKS_ENABLED": "true",
                "HEALTHCHECKS_API_URL": "https://healthchecks.example.test/api/v3",
                "HEALTHCHECKS_API_KEY": "secret-value",
            },
            clear=False,
        ):
            snapshot = healthchecks_snapshot()

        self.assertEqual(snapshot.state, "unavailable")
        self.assertIn("interpret", snapshot.detail)

    @patch("integrations.healthchecks.httpx.get")
    def test_disabled_integration_never_calls_api(self, mocked_get):
        with patch.dict(os.environ, {"HEALTHCHECKS_ENABLED": "false"}, clear=False):
            snapshot = healthchecks_snapshot()

        self.assertEqual(snapshot.state, "disabled")
        mocked_get.assert_not_called()

    @patch("integrations.healthchecks.httpx.get")
    def test_missing_required_configuration_is_misconfigured(self, mocked_get):
        with patch.dict(
            os.environ,
            {
                "HEALTHCHECKS_ENABLED": "true",
                "HEALTHCHECKS_API_URL": "",
                "HEALTHCHECKS_API_KEY": "",
            },
            clear=False,
        ):
            snapshot = healthchecks_snapshot()

        self.assertEqual(snapshot.state, "misconfigured")
        self.assertIn("HEALTHCHECKS_API_URL", snapshot.detail)
        self.assertIn("HEALTHCHECKS_API_KEY", snapshot.detail)
        mocked_get.assert_not_called()
