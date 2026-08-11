"""Tests for the read-only Uptime Kuma metrics integration."""

import os
from datetime import UTC, datetime
from unittest.mock import patch

import httpx
from django.test import SimpleTestCase

from integrations.uptime_kuma import _parse_metrics, uptime_kuma_snapshot


SAMPLE_METRICS = r'''
# HELP monitor_status Monitor Status
# TYPE monitor_status gauge
monitor_status{monitor_name="Caddy",monitor_type="http",monitor_url="https://secret-target.invalid/",monitor_hostname="",monitor_port=""} 1
monitor_response_time{monitor_name="Caddy",monitor_type="http",monitor_url="https://secret-target.invalid/",monitor_hostname="",monitor_port=""} 23
monitor_status{monitor_name="Vaultwarden",monitor_type="http",monitor_url="https://vault.invalid/",monitor_hostname="",monitor_port=""} 0
monitor_response_time{monitor_name="Vaultwarden",monitor_type="http",monitor_url="https://vault.invalid/",monitor_hostname="",monitor_port=""} 147.5
monitor_status{monitor_name="Maintenance test",monitor_type="ping",monitor_url="",monitor_hostname="private.internal",monitor_port=""} 3
'''


class UptimeKumaMetricsParserTests(SimpleTestCase):
    def test_parser_keeps_only_approved_monitor_fields(self):
        snapshot = _parse_metrics(
            SAMPLE_METRICS,
            observed_at=datetime(2026, 8, 11, 21, 30, tzinfo=UTC),
        )

        self.assertEqual(snapshot.state, "degraded")
        self.assertEqual(snapshot.total, 3)
        self.assertEqual(snapshot.up, 1)
        self.assertEqual(snapshot.down, 1)
        self.assertEqual(snapshot.maintenance, 1)
        self.assertEqual(snapshot.attention, 1)

        caddy = next(monitor for monitor in snapshot.monitors if monitor.name == "Caddy")
        self.assertEqual(caddy.monitor_type, "http")
        self.assertEqual(caddy.state, "up")
        self.assertEqual(caddy.response_time_label, "23 ms")

        representation = repr(snapshot)
        self.assertNotIn("secret-target.invalid", representation)
        self.assertNotIn("private.internal", representation)

    def test_empty_monitor_metrics_degrade_cleanly(self):
        snapshot = _parse_metrics(
            "# no monitor samples\n",
            observed_at=datetime(2026, 8, 11, 21, 30, tzinfo=UTC),
        )

        self.assertEqual(snapshot.state, "degraded")
        self.assertEqual(snapshot.total, 0)


class UptimeKumaAdapterTests(SimpleTestCase):
    def test_disabled_integration_does_not_require_secret(self):
        with patch.dict(os.environ, {"UPTIME_KUMA_ENABLED": "false"}, clear=False):
            snapshot = uptime_kuma_snapshot()

        self.assertEqual(snapshot.state, "disabled")

    def test_missing_key_is_misconfigured(self):
        with patch.dict(
            os.environ,
            {
                "UPTIME_KUMA_ENABLED": "true",
                "UPTIME_KUMA_METRICS_URL": "http://uptime-kuma:3001/metrics",
                "UPTIME_KUMA_API_KEY": "",
            },
            clear=False,
        ):
            snapshot = uptime_kuma_snapshot()

        self.assertEqual(snapshot.state, "misconfigured")
        self.assertIn("UPTIME_KUMA_API_KEY", snapshot.detail)

    @patch("integrations.uptime_kuma.httpx.get")
    def test_live_metrics_are_normalized(self, mocked_get):
        mocked_get.return_value = httpx.Response(
            200,
            text=SAMPLE_METRICS,
            request=httpx.Request("GET", "http://uptime-kuma:3001/metrics"),
        )

        secret = "uk9_" + "a" * 40
        with patch.dict(
            os.environ,
            {
                "UPTIME_KUMA_ENABLED": "true",
                "UPTIME_KUMA_METRICS_URL": "http://uptime-kuma:3001/metrics",
                "UPTIME_KUMA_API_KEY": secret,
            },
            clear=False,
        ):
            snapshot = uptime_kuma_snapshot()

        self.assertEqual(snapshot.state, "degraded")
        self.assertEqual(snapshot.total, 3)
        self.assertNotIn(secret, repr(snapshot))
        self.assertEqual(mocked_get.call_args.args[0], "http://uptime-kuma:3001/metrics")
        self.assertIsInstance(mocked_get.call_args.kwargs["auth"], httpx.BasicAuth)

    @patch("integrations.uptime_kuma.httpx.get")
    def test_invalid_key_fails_soft_without_echoing_key(self, mocked_get):
        mocked_get.return_value = httpx.Response(
            401,
            text="Unauthorized",
            request=httpx.Request("GET", "http://uptime-kuma:3001/metrics"),
        )

        secret = "uk3_" + "b" * 40
        with patch.dict(
            os.environ,
            {
                "UPTIME_KUMA_ENABLED": "true",
                "UPTIME_KUMA_METRICS_URL": "http://uptime-kuma:3001/metrics",
                "UPTIME_KUMA_API_KEY": secret,
            },
            clear=False,
        ):
            snapshot = uptime_kuma_snapshot()

        self.assertEqual(snapshot.state, "unavailable")
        self.assertIn("rejected", snapshot.detail)
        self.assertNotIn(secret, repr(snapshot))

    @patch("integrations.uptime_kuma.httpx.get")
    def test_unreachable_endpoint_fails_soft(self, mocked_get):
        mocked_get.side_effect = httpx.ConnectError("refused")

        with patch.dict(
            os.environ,
            {
                "UPTIME_KUMA_ENABLED": "true",
                "UPTIME_KUMA_METRICS_URL": "http://uptime-kuma:3001/metrics",
                "UPTIME_KUMA_API_KEY": "uk1_" + "c" * 40,
            },
            clear=False,
        ):
            snapshot = uptime_kuma_snapshot()

        self.assertEqual(snapshot.state, "unavailable")
        self.assertIn("could not reach", snapshot.detail.lower())
