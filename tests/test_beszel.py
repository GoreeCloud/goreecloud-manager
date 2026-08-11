"""Tests for the delegated read-only Beszel status artifact."""

from __future__ import annotations

import json
import os
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from django.test import SimpleTestCase

from integrations.beszel import beszel_status


class BeszelAdapterTests(SimpleTestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.status_path = Path(self.tempdir.name) / "status.json"
        self.now = datetime(2026, 8, 11, 22, 30, tzinfo=UTC)

    def _payload(
        self,
        *,
        generated_at: datetime | None = None,
        observed_at: datetime | None = None,
        collector_state: str = "ok",
        system_status: str = "up",
    ):
        generated = generated_at or (self.now - timedelta(minutes=2))
        observed = observed_at or (self.now - timedelta(minutes=5))
        return {
            "schema_version": 1,
            "generated_at": generated.isoformat().replace("+00:00", "Z"),
            "collector": {
                "state": collector_state,
                "checked_at": generated.isoformat().replace("+00:00", "Z"),
            },
            "source": {
                "name": "goreecloud-vps-01",
                "status": system_status,
                "updated_at": generated.isoformat().replace("+00:00", "Z"),
                "agent_version": "0.18.7",
                "beszel_version": "0.18.7",
            },
            "stats": {
                "observed_at": observed.isoformat().replace("+00:00", "Z"),
                "cpu_percent": 5.03,
                "load_average": [0.15, 0.12, 0.08],
                "memory_total_gb": 7.58,
                "memory_used_gb": 4.18,
                "memory_percent": 55.19,
                "swap_total_gb": 2.0,
                "swap_used_gb": 0.11,
                "disk_total_gb": 73.62,
                "disk_used_gb": 21.02,
                "disk_percent": 29.78,
                "network": {
                    "sent_bytes": 1000,
                    "recv_bytes": 2000,
                },
                "temperatures": {},
            },
            "details": {
                "hostname": "goreecloud-vps-01",
                "kernel": "6.12.96+deb13-amd64",
                "cores": 4,
                "threads": 4,
                "cpu_model": "Intel Core Processor (Haswell, no TSX)",
                "os_name": "Debian GNU/Linux 13 (trixie)",
                "architecture": "x86_64",
                "memory_bytes": 8134107136,
                "podman": False,
            },
            "containers": [
                {
                    "name": "caddy",
                    "state": "Up 4 days",
                    "health": "healthy",
                    "cpu_percent": 0.2,
                    "memory_gb": 0.05,
                    "network": {
                        "sent_bytes": 300,
                        "recv_bytes": 500,
                    },
                },
                {
                    "name": "beszel",
                    "state": "Up 3 days",
                    "health": "healthy",
                    "cpu_percent": 0.4,
                    "memory_gb": 0.08,
                    "network": {
                        "sent_bytes": 100,
                        "recv_bytes": 200,
                    },
                },
            ],
        }

    def _write(self, payload):
        self.status_path.write_text(json.dumps(payload), encoding="utf-8")

    def _environment(self):
        return {
            "BESZEL_ENABLED": "true",
            "BESZEL_STATUS_PATH": str(self.status_path),
            "BESZEL_STATUS_MAX_AGE_SECONDS": "900",
            "BESZEL_DATA_MAX_AGE_SECONDS": "1800",
        }

    def test_healthy_artifact_normalizes_approved_resource_fields(self):
        self._write(self._payload())

        with patch.dict(os.environ, self._environment(), clear=False):
            status = beszel_status(now=self.now)

        self.assertEqual(status.state, "healthy")
        self.assertEqual(status.source_name, "goreecloud-vps-01")
        self.assertEqual(status.source_status, "up")
        self.assertEqual(status.agent_version, "0.18.7")
        self.assertEqual(status.beszel_version, "0.18.7")
        self.assertEqual(status.stats.cpu_label, "5.0%")
        self.assertEqual(status.stats.memory_label, "4.18 / 7.58 GB")
        self.assertEqual(status.stats.disk_percent_label, "29.8%")
        self.assertEqual(status.details.cores, 4)
        self.assertEqual(status.container_total, 2)
        self.assertEqual(status.container_attention, 0)
        self.assertEqual(status.containers[0].name, "beszel")
        self.assertNotIn("password", repr(status).lower())
        self.assertNotIn("token", repr(status).lower())

    def test_stale_artifact_degrades(self):
        self._write(self._payload(generated_at=self.now - timedelta(minutes=20)))

        with patch.dict(os.environ, self._environment(), clear=False):
            status = beszel_status(now=self.now)

        self.assertEqual(status.state, "degraded")
        self.assertIn("status artifact is stale", status.detail)

    def test_stale_resource_data_degrades(self):
        self._write(self._payload(observed_at=self.now - timedelta(minutes=31)))

        with patch.dict(os.environ, self._environment(), clear=False):
            status = beszel_status(now=self.now)

        self.assertEqual(status.state, "degraded")
        self.assertIn("resource data is stale", status.detail)

    def test_non_up_system_state_degrades(self):
        self._write(self._payload(system_status="down"))

        with patch.dict(os.environ, self._environment(), clear=False):
            status = beszel_status(now=self.now)

        self.assertEqual(status.state, "degraded")
        self.assertIn("system state down", status.detail)

    def test_collector_auth_failure_with_previous_data_degrades(self):
        self._write(self._payload(collector_state="auth_error"))

        with patch.dict(os.environ, self._environment(), clear=False):
            status = beszel_status(now=self.now)

        self.assertEqual(status.state, "degraded")
        self.assertIn("authentication failed", status.detail)
        self.assertEqual(status.container_total, 2)

    def test_collector_auth_failure_without_data_is_fail_soft(self):
        payload = self._payload(collector_state="auth_error")
        payload["source"] = None
        payload["stats"] = None
        payload["details"] = None
        payload["containers"] = []
        self._write(payload)

        with patch.dict(os.environ, self._environment(), clear=False):
            status = beszel_status(now=self.now)

        self.assertEqual(status.state, "unavailable")
        self.assertEqual(status.detail, "Delegated Beszel collector authentication failed.")

    def test_missing_artifact_is_fail_soft(self):
        with patch.dict(os.environ, self._environment(), clear=False):
            status = beszel_status(now=self.now)

        self.assertEqual(status.state, "unavailable")
        self.assertEqual(status.detail, "Beszel status artifact is not available.")

    def test_malformed_artifact_is_fail_soft(self):
        self.status_path.write_text("not-json", encoding="utf-8")

        with patch.dict(os.environ, self._environment(), clear=False):
            status = beszel_status(now=self.now)

        self.assertEqual(status.state, "unavailable")
        self.assertEqual(status.detail, "Beszel status artifact is malformed.")

    def test_unsupported_schema_is_fail_soft(self):
        payload = self._payload()
        payload["schema_version"] = 999
        self._write(payload)

        with patch.dict(os.environ, self._environment(), clear=False):
            status = beszel_status(now=self.now)

        self.assertEqual(status.state, "unavailable")
        self.assertIn("schema is not supported", status.detail)

    def test_disabled_adapter_does_not_read_artifact(self):
        with patch.dict(os.environ, {"BESZEL_ENABLED": "false"}, clear=False):
            status = beszel_status(now=self.now)

        self.assertEqual(status.state, "disabled")
        self.assertEqual(status.detail, "Native Beszel resource visibility is disabled.")
