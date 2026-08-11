"""Tests for the read-only NetBird integration."""

import os
from unittest.mock import Mock, patch

import httpx
from django.test import SimpleTestCase

from integrations.netbird import netbird_snapshot


class NetBirdAdapterTests(SimpleTestCase):
    def _response(self, *, status_code=200, payload=None):
        response = Mock()
        response.status_code = status_code
        response.json.return_value = [] if payload is None else payload
        response.raise_for_status.return_value = None
        return response

    @patch("integrations.netbird.httpx.get")
    def test_success_normalizes_peer_data_and_counts(self, mocked_get):
        mocked_get.return_value = self._response(
            payload=[
                {
                    "id": "peer-2",
                    "name": "offline-peer",
                    "dns_label": "offline-peer.netbird.selfhosted",
                    "ip": "100.64.0.2",
                    "connected": False,
                    "last_seen": "2026-08-11T06:00:00Z",
                    "os": "linux",
                    "version": "0.58.2",
                },
                {
                    "id": "peer-1",
                    "name": "online-peer",
                    "dns_label": "online-peer.netbird.selfhosted",
                    "ip": "100.64.0.1",
                    "ipv6": "fd00::1",
                    "connected": True,
                    "last_seen": "2026-08-11T07:00:00Z",
                    "os": "linux",
                    "version": "0.58.2",
                },
            ]
        )

        with patch.dict(
            os.environ,
            {
                "NETBIRD_ENABLED": "true",
                "NETBIRD_API_URL": "https://netbird.example.test/api",
                "NETBIRD_API_TOKEN": "test-token",
            },
            clear=False,
        ):
            snapshot = netbird_snapshot()

        self.assertEqual(snapshot.state, "healthy")
        self.assertEqual(snapshot.total, 2)
        self.assertEqual(snapshot.connected, 1)
        self.assertEqual(snapshot.disconnected, 1)
        self.assertEqual(snapshot.peers[0].name, "online-peer")
        self.assertEqual(snapshot.peers[0].ipv6, "fd00::1")
        self.assertIsNotNone(snapshot.peers[0].last_seen)
        _, kwargs = mocked_get.call_args
        self.assertEqual(kwargs["headers"]["Authorization"], "Token test-token")
        self.assertNotIn("test-token", snapshot.detail)

    @patch("integrations.netbird.httpx.get")
    def test_timeout_degrades_to_unavailable(self, mocked_get):
        mocked_get.side_effect = httpx.TimeoutException("slow")
        with patch.dict(
            os.environ,
            {
                "NETBIRD_ENABLED": "true",
                "NETBIRD_API_URL": "https://netbird.example.test/api",
                "NETBIRD_API_TOKEN": "secret-value",
            },
            clear=False,
        ):
            snapshot = netbird_snapshot()

        self.assertEqual(snapshot.state, "unavailable")
        self.assertIn("timeout", snapshot.detail)
        self.assertNotIn("secret-value", snapshot.detail)

    @patch("integrations.netbird.httpx.get")
    def test_authentication_failure_is_sanitized(self, mocked_get):
        mocked_get.return_value = self._response(status_code=401)
        with patch.dict(
            os.environ,
            {
                "NETBIRD_ENABLED": "true",
                "NETBIRD_API_URL": "https://netbird.example.test/api",
                "NETBIRD_API_TOKEN": "secret-value",
            },
            clear=False,
        ):
            snapshot = netbird_snapshot()

        self.assertEqual(snapshot.state, "unavailable")
        self.assertIn("credential", snapshot.detail)
        self.assertNotIn("secret-value", snapshot.detail)

    @patch("integrations.netbird.httpx.get")
    def test_malformed_response_is_unavailable(self, mocked_get):
        mocked_get.return_value = self._response(payload={"unexpected": "object"})
        with patch.dict(
            os.environ,
            {
                "NETBIRD_ENABLED": "true",
                "NETBIRD_API_URL": "https://netbird.example.test/api",
                "NETBIRD_API_TOKEN": "secret-value",
            },
            clear=False,
        ):
            snapshot = netbird_snapshot()

        self.assertEqual(snapshot.state, "unavailable")
        self.assertIn("interpret", snapshot.detail)

    @patch("integrations.netbird.httpx.get")
    def test_disabled_integration_never_calls_api(self, mocked_get):
        with patch.dict(os.environ, {"NETBIRD_ENABLED": "false"}, clear=False):
            snapshot = netbird_snapshot()

        self.assertEqual(snapshot.state, "disabled")
        mocked_get.assert_not_called()

    @patch("integrations.netbird.httpx.get")
    def test_missing_required_configuration_is_misconfigured(self, mocked_get):
        with patch.dict(
            os.environ,
            {
                "NETBIRD_ENABLED": "true",
                "NETBIRD_API_URL": "",
                "NETBIRD_API_TOKEN": "",
            },
            clear=False,
        ):
            snapshot = netbird_snapshot()

        self.assertEqual(snapshot.state, "misconfigured")
        self.assertIn("NETBIRD_API_URL", snapshot.detail)
        self.assertIn("NETBIRD_API_TOKEN", snapshot.detail)
        mocked_get.assert_not_called()
