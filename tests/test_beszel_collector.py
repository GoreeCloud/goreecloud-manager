"""Tests for the host-side Beszel collector sanitization boundary."""

from __future__ import annotations

import importlib.util
import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from django.test import SimpleTestCase


COLLECTOR_PATH = Path(__file__).resolve().parents[1] / "ops" / "beszel-status-collector.py"
SPEC = importlib.util.spec_from_file_location("beszel_status_collector", COLLECTOR_PATH)
assert SPEC and SPEC.loader
collector = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(collector)


class BeszelCollectorTests(SimpleTestCase):
    def test_normalize_system_keeps_only_approved_fields(self):
        normalized = collector.normalize_system(
            system={
                "id": "system-secret-id-not-needed",
                "name": "goreecloud-vps-01",
                "host": "internal-target.example",
                "port": "45876",
                "status": "up",
                "updated": "2026-08-11T22:17:52Z",
                "users": ["user-id"],
                "info": {
                    "cpu": 5.03,
                    "mp": 55.19,
                    "dp": 29.78,
                    "la": [0.10, 0.20, 0.30],
                    "t": 4,
                    "u": 1740557,
                    "v": "0.18.7",
                },
            },
            beszel_version="0.18.7",
            stats_record={
                "created": "2026-08-11T22:20:00Z",
                "stats": {
                    "cpu": 5.03,
                    "m": 7.58,
                    "mu": 4.18,
                    "mp": 55.19,
                    "s": 2,
                    "su": 0.11,
                    "d": 73.62,
                    "du": 21.02,
                    "dp": 29.78,
                    "la": [0.10, 0.20, 0.30],
                    "b": [1000, 2000],
                    "t": {"Package id 0": 42.0},
                },
            },
            details_record={
                "hostname": "goreecloud-vps-01",
                "kernel": "6.12.96+deb13-amd64",
                "cores": 4,
                "threads": 4,
                "cpu": "Intel Core Processor",
                "os": 0,
                "os_name": "Debian GNU/Linux 13 (trixie)",
                "arch": "x86_64",
                "memory": 8134107136,
                "podman": False,
                "unapproved": "drop-me",
            },
            container_records=[
                {
                    "id": "container-record-id",
                    "name": "caddy",
                    "image": "secret-registry/image",
                    "ports": "443/tcp",
                    "status": "Up 4 days",
                    "health": 2,
                    "cpu": 9.9,
                    "memory": 1.0,
                }
            ],
            container_stats_record={
                "created": "2026-08-11T22:20:00Z",
                "stats": [
                    {
                        "n": "caddy",
                        "c": 0.2,
                        "m": 0.05,
                        "b": [300, 500],
                    }
                ],
            },
        )

        self.assertEqual(normalized["source"]["name"], "goreecloud-vps-01")
        self.assertEqual(normalized["stats"]["memory_used_gb"], 4.18)
        self.assertEqual(normalized["stats"]["network"]["sent_bytes"], 1000)
        self.assertEqual(normalized["details"]["memory_bytes"], 8134107136)
        self.assertEqual(normalized["containers"][0]["name"], "caddy")
        self.assertEqual(normalized["containers"][0]["cpu_percent"], 0.2)
        self.assertEqual(normalized["containers"][0]["health"], "healthy")

        serialized = repr(normalized)
        self.assertNotIn("internal-target.example", serialized)
        self.assertNotIn("system-secret-id-not-needed", serialized)
        self.assertNotIn("container-record-id", serialized)
        self.assertNotIn("secret-registry", serialized)
        self.assertNotIn("443/tcp", serialized)
        self.assertNotIn("users", serialized)
        self.assertNotIn("unapproved", serialized)

    def test_build_failure_payload_preserves_only_previous_sanitized_data(self):
        now = datetime(2026, 8, 11, 22, 30, tzinfo=UTC)
        previous = {
            "source": {"name": "goreecloud-vps-01"},
            "stats": {"cpu_percent": 5.0},
            "details": {"hostname": "goreecloud-vps-01"},
            "containers": [{"name": "caddy"}],
        }

        payload = collector.build_payload(
            now=now,
            collector_state="auth_error",
            data=previous,
        )

        self.assertEqual(payload["collector"]["state"], "auth_error")
        self.assertEqual(payload["source"], previous["source"])
        self.assertNotIn("password", repr(payload).lower())
        self.assertNotIn("token", repr(payload).lower())

    def test_atomic_write_creates_non_secret_readable_artifact(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "beszel" / "status.json"
            payload = {
                "schema_version": 1,
                "generated_at": "2026-08-11T22:30:00Z",
                "collector": {
                    "state": "ok",
                    "checked_at": "2026-08-11T22:30:00Z",
                },
            }

            collector.atomic_write(path, payload)

            self.assertTrue(path.exists())
            self.assertIn('"schema_version": 1', path.read_text(encoding="utf-8"))
            self.assertEqual(os.stat(path).st_mode & 0o777, 0o644)
            self.assertEqual(os.stat(path.parent).st_mode & 0o777, 0o755)

    def test_parse_timestamp_accepts_live_beszel_timestamp(self):
        parsed = collector.parse_timestamp("2026-08-11 22:17:52.135Z")
        self.assertEqual(
            parsed,
            datetime(2026, 8, 11, 22, 17, 52, 135000, tzinfo=UTC),
        )
