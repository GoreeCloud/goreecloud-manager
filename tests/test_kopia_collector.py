"""Tests for the host-side Kopia status collector's sanitization boundary."""

from __future__ import annotations

import importlib.util
import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from django.test import SimpleTestCase


COLLECTOR_PATH = Path(__file__).resolve().parents[1] / "ops" / "kopia-status-collector.py"
SPEC = importlib.util.spec_from_file_location("kopia_status_collector", COLLECTOR_PATH)
assert SPEC and SPEC.loader
collector = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(collector)


class KopiaCollectorTests(SimpleTestCase):
    def test_normalize_snapshot_uses_total_summary_and_drops_sensitive_fields(self):
        normalized = collector.normalize_snapshot(
            {
                "id": "snapshot-id",
                "source": {
                    "host": "goreecloud-vps-01",
                    "userName": "root",
                    "path": "/source",
                },
                "description": "Scheduled GoreeCloud VPS backup to laptop SFTP repository",
                "startTime": "2026-08-11T03:33:28Z",
                "endTime": "2026-08-11T03:33:30Z",
                "stats": {
                    "totalSize": 10,
                    "fileCount": 83,
                    "errorCount": 9,
                },
                "rootEntry": {
                    "obj": "must-not-leave-collector",
                    "summ": {
                        "size": 484991682,
                        "files": 1507,
                        "dirs": 207,
                        "numFailed": 0,
                    },
                },
                "retentionReason": ["latest-1", "daily-1"],
            }
        )

        self.assertEqual(normalized["id"], "snapshot-id")
        self.assertEqual(normalized["size_bytes"], 484991682)
        self.assertEqual(normalized["file_count"], 1507)
        self.assertEqual(normalized["directory_count"], 207)
        self.assertEqual(normalized["error_count"], 0)
        self.assertEqual(normalized["retention_reasons"], ["latest-1", "daily-1"])
        self.assertNotIn("source", normalized)
        self.assertNotIn("obj", repr(normalized))
        self.assertNotIn("userName", repr(normalized))
        self.assertNotIn("root", repr(normalized))

    def test_atomic_write_creates_non_secret_readable_artifact(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "kopia" / "status.json"
            payload = {
                "schema_version": 1,
                "generated_at": "2026-08-11T13:00:00Z",
                "latest_snapshot": None,
            }

            collector.atomic_write(path, payload)

            self.assertTrue(path.exists())
            self.assertIn('"schema_version": 1', path.read_text(encoding="utf-8"))
            self.assertEqual(os.stat(path).st_mode & 0o777, 0o644)
            self.assertEqual(os.stat(path.parent).st_mode & 0o777, 0o755)

    def test_parse_timestamp_accepts_precise_bootstrap_event_time(self):
        parsed = collector.parse_timestamp("2026-08-11T11:03:41Z")
        self.assertEqual(parsed, datetime(2026, 8, 11, 11, 3, 41, tzinfo=UTC))
