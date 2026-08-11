"""Tests for the delegated read-only Kopia status artifact."""

from __future__ import annotations

import json
import os
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from django.test import SimpleTestCase

from integrations.kopia import kopia_status


class KopiaAdapterTests(SimpleTestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.status_path = Path(self.tempdir.name) / "status.json"
        self.now = datetime(2026, 8, 11, 13, 0, tzinfo=UTC)

    def _payload(
        self,
        *,
        generated_at: datetime | None = None,
        attempt_state: str = "success",
        attempt_reason: str = "snapshot-created",
        repository_state: str = "ok",
        snapshot_end: datetime | None = None,
        error_count: int = 0,
    ):
        generated = generated_at or (self.now - timedelta(minutes=5))
        end = snapshot_end or (self.now - timedelta(hours=2))
        start = end - timedelta(seconds=2)

        return {
            "schema_version": 1,
            "generated_at": generated.isoformat().replace("+00:00", "Z"),
            "source": {
                "host": "goreecloud-vps-01",
                "label": "GoreeCloud VPS protected data",
            },
            "repository_query": {
                "state": repository_state,
                "checked_at": generated.isoformat().replace("+00:00", "Z")
                if repository_state == "ok"
                else None,
            },
            "latest_attempt": {
                "state": attempt_state,
                "at": end.isoformat().replace("+00:00", "Z"),
                "reason": attempt_reason,
            },
            "latest_snapshot": {
                "id": "snapshot-test-id",
                "start_time": start.isoformat().replace("+00:00", "Z"),
                "end_time": end.isoformat().replace("+00:00", "Z"),
                "description": "Scheduled GoreeCloud VPS backup to laptop SFTP repository",
                "size_bytes": 484991682,
                "file_count": 1507,
                "directory_count": 207,
                "error_count": error_count,
                "retention_reasons": ["latest-1", "daily-1"],
            },
        }

    def _write(self, payload):
        self.status_path.write_text(json.dumps(payload), encoding="utf-8")

    def _environment(self):
        return {
            "KOPIA_ENABLED": "true",
            "KOPIA_STATUS_PATH": str(self.status_path),
            "KOPIA_STATUS_MAX_AGE_SECONDS": "28800",
            "KOPIA_SNAPSHOT_MAX_AGE_SECONDS": "43200",
        }

    def test_healthy_artifact_normalizes_approved_snapshot_fields(self):
        self._write(self._payload())

        with patch.dict(os.environ, self._environment(), clear=False):
            status = kopia_status(now=self.now)

        self.assertEqual(status.state, "healthy")
        self.assertEqual(status.source_host, "goreecloud-vps-01")
        self.assertEqual(status.repository_state, "ok")
        self.assertEqual(status.latest_attempt.state, "success")
        self.assertEqual(status.latest_snapshot.snapshot_id, "snapshot-test-id")
        self.assertEqual(status.latest_snapshot.file_count, 1507)
        self.assertEqual(status.latest_snapshot.directory_count, 207)
        self.assertEqual(status.latest_snapshot.error_count, 0)
        self.assertEqual(status.latest_snapshot.size_label, "462.5 MiB")
        self.assertEqual(status.snapshot_age_label, "2 hours")
        self.assertNotIn("password", repr(status).lower())

    def test_skipped_attempt_degrades_without_discarding_last_snapshot(self):
        payload = self._payload(
            attempt_state="skipped",
            attempt_reason="target-unavailable",
            repository_state="not_attempted",
        )
        self._write(payload)

        with patch.dict(os.environ, self._environment(), clear=False):
            status = kopia_status(now=self.now)

        self.assertEqual(status.state, "degraded")
        self.assertIn("latest scheduled backup attempt was skipped", status.detail)
        self.assertEqual(status.latest_snapshot.snapshot_id, "snapshot-test-id")
        self.assertEqual(status.latest_attempt.reason_label, "Backup target unavailable")

    def test_failed_attempt_degrades(self):
        self._write(
            self._payload(
                attempt_state="failed",
                attempt_reason="snapshot-failed",
                repository_state="not_attempted",
            )
        )

        with patch.dict(os.environ, self._environment(), clear=False):
            status = kopia_status(now=self.now)

        self.assertEqual(status.state, "degraded")
        self.assertIn("latest backup attempt failed", status.detail)

    def test_stale_artifact_and_old_snapshot_degrade(self):
        self._write(
            self._payload(
                generated_at=self.now - timedelta(hours=9),
                snapshot_end=self.now - timedelta(hours=13),
            )
        )

        with patch.dict(os.environ, self._environment(), clear=False):
            status = kopia_status(now=self.now)

        self.assertEqual(status.state, "degraded")
        self.assertIn("status artifact is stale", status.detail)
        self.assertIn("latest snapshot is older", status.detail)

    def test_snapshot_errors_degrade(self):
        self._write(self._payload(error_count=2))

        with patch.dict(os.environ, self._environment(), clear=False):
            status = kopia_status(now=self.now)

        self.assertEqual(status.state, "degraded")
        self.assertIn("latest snapshot reports errors", status.detail)

    def test_missing_artifact_is_fail_soft(self):
        with patch.dict(os.environ, self._environment(), clear=False):
            status = kopia_status(now=self.now)

        self.assertEqual(status.state, "unavailable")
        self.assertEqual(status.detail, "Kopia status artifact is not available.")

    def test_malformed_artifact_is_fail_soft(self):
        self.status_path.write_text("not-json", encoding="utf-8")

        with patch.dict(os.environ, self._environment(), clear=False):
            status = kopia_status(now=self.now)

        self.assertEqual(status.state, "unavailable")
        self.assertEqual(status.detail, "Kopia status artifact is malformed.")

    def test_unsupported_schema_is_fail_soft(self):
        payload = self._payload()
        payload["schema_version"] = 999
        self._write(payload)

        with patch.dict(os.environ, self._environment(), clear=False):
            status = kopia_status(now=self.now)

        self.assertEqual(status.state, "unavailable")
        self.assertIn("schema is not supported", status.detail)

    def test_disabled_adapter_does_not_read_artifact(self):
        with patch.dict(os.environ, {"KOPIA_ENABLED": "false"}, clear=False):
            status = kopia_status(now=self.now)

        self.assertEqual(status.state, "disabled")
        self.assertEqual(status.detail, "Native Kopia status visibility is disabled.")
