"""Regression tests for bounded expired-session maintenance."""

from __future__ import annotations

from datetime import timedelta
from io import StringIO

from django.contrib.sessions.models import Session
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from django.utils import timezone


class SessionMaintenanceTests(TestCase):
    def _create_session(self, key: str, *, expired: bool, payload: str = "") -> Session:
        now = timezone.now()
        return Session.objects.create(
            session_key=key,
            session_data=payload,
            expire_date=now - timedelta(minutes=5) if expired else now + timedelta(hours=1),
        )

    def test_dry_run_reports_expired_count_without_deleting(self):
        self._create_session("expired-dry-run", expired=True)
        self._create_session("active-dry-run", expired=False)
        stdout = StringIO()

        call_command("prune_expired_sessions", "--dry-run", stdout=stdout)

        self.assertEqual(Session.objects.count(), 2)
        self.assertEqual(
            stdout.getvalue().strip(),
            "expired_sessions=1 deleted_sessions=0 dry_run=true",
        )

    def test_cleanup_deletes_only_expired_sessions(self):
        self._create_session("expired-delete", expired=True)
        self._create_session("active-preserved", expired=False)
        stdout = StringIO()

        call_command("prune_expired_sessions", stdout=stdout)

        self.assertFalse(Session.objects.filter(session_key="expired-delete").exists())
        self.assertTrue(Session.objects.filter(session_key="active-preserved").exists())
        self.assertEqual(
            stdout.getvalue().strip(),
            "expired_sessions=1 deleted_sessions=1 dry_run=false",
        )

    def test_cleanup_processes_multiple_bounded_batches(self):
        for index in range(5):
            self._create_session(f"expired-batch-{index}", expired=True)
        self._create_session("active-batch", expired=False)
        stdout = StringIO()

        call_command("prune_expired_sessions", "--batch-size", "2", stdout=stdout)

        self.assertEqual(Session.objects.filter(expire_date__lt=timezone.now()).count(), 0)
        self.assertTrue(Session.objects.filter(session_key="active-batch").exists())
        self.assertEqual(
            stdout.getvalue().strip(),
            "expired_sessions=5 deleted_sessions=5 dry_run=false",
        )

    def test_cleanup_output_excludes_session_identifiers_and_payloads(self):
        sensitive_key = "sensitive-session-key-marker"
        sensitive_payload = "sensitive-session-payload-marker"
        self._create_session(
            sensitive_key,
            expired=True,
            payload=sensitive_payload,
        )
        stdout = StringIO()

        call_command("prune_expired_sessions", stdout=stdout)

        output = stdout.getvalue()
        self.assertNotIn(sensitive_key, output)
        self.assertNotIn(sensitive_payload, output)
        self.assertIn("expired_sessions=1", output)
        self.assertIn("deleted_sessions=1", output)

    def test_cleanup_rejects_unbounded_batch_sizes(self):
        for invalid_batch_size in ("0", "1001"):
            with self.subTest(batch_size=invalid_batch_size):
                with self.assertRaises(CommandError):
                    call_command(
                        "prune_expired_sessions",
                        "--batch-size",
                        invalid_batch_size,
                    )
