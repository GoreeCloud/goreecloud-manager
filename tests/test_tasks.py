"""Tests for the read-only GoreeCloud Tasks integration."""

import os
from unittest.mock import Mock, patch

import httpx
from django.test import SimpleTestCase

from integrations.tasks import tasks_snapshot


class TasksAdapterTests(SimpleTestCase):
    TOKEN = "manager-adapter-test-token-0123456789abcdef0123456789abcdef"

    def _response(self, *, status_code=200, payload=None):
        response = Mock()
        response.status_code = status_code
        response.json.return_value = payload
        response.raise_for_status.return_value = None
        return response

    def _payload(self):
        return {
            "schema": "goreecloud.tasks.manager.v1",
            "version": 1,
            "generated_at": "2026-08-12T11:20:00-05:00",
            "authorization": {
                "identity": "goreecloud-manager-integration",
                "scope": "visible operational project tasks only",
            },
            "summary": {
                "total_open": 2,
                "blocked": 1,
                "p0": 0,
                "p1": 1,
                "returned": 1,
            },
            "tasks": [
                {
                    "id": 42,
                    "title": "Validate backup recovery path",
                    "project": {"id": 7, "name": "Infrastructure Work"},
                    "priority": {"value": 1, "label": "P1 — Urgent"},
                    "status": {"value": "blocked", "label": "Blocked"},
                    "due_at": "2026-08-13T09:00:00-05:00",
                    "assigned_system": "Infrastructure Services VM",
                    "assigned_service": "Kopia",
                    "environment": "production-planning",
                    "workload_category": "Recovery",
                    "blocker": "Restore test not yet completed",
                    "resume_condition": "Complete isolated restore validation",
                    "requirements": {
                        "backup": True,
                        "recovery": True,
                        "validation": True,
                        "documentation": True,
                    },
                    "related_change_record": "GoreeCloud Tasks change log",
                    "related_documentation": "Backup and recovery standard",
                    "updated_at": "2026-08-12T11:15:00-05:00",
                }
            ],
        }

    def _environment(self, **overrides):
        values = {
            "TASKS_ENABLED": "true",
            "TASKS_API_URL": "https://tasks.example.test",
            "TASKS_ACCESS_TOKEN": self.TOKEN,
            "TASKS_ACCESS_TOKEN_FILE": "",
            "TASKS_TIMEOUT_SECONDS": "5",
        }
        values.update(overrides)
        return patch.dict(os.environ, values, clear=False)

    @patch("integrations.tasks.httpx.get")
    def test_success_normalizes_scoped_operational_tasks(self, mocked_get):
        mocked_get.return_value = self._response(payload=self._payload())

        with self._environment():
            snapshot = tasks_snapshot()

        self.assertEqual(snapshot.state, "healthy")
        self.assertEqual(snapshot.total_open, 2)
        self.assertEqual(snapshot.blocked, 1)
        self.assertEqual(snapshot.p0, 0)
        self.assertEqual(snapshot.p1, 1)
        self.assertEqual(snapshot.returned, 1)
        self.assertEqual(snapshot.identity, "goreecloud-manager-integration")
        task = snapshot.tasks[0]
        self.assertEqual(task.task_id, 42)
        self.assertEqual(task.project_name, "Infrastructure Work")
        self.assertEqual(task.assigned_service, "Kopia")
        self.assertTrue(task.recovery_required)
        self.assertEqual(task.status, "blocked")

        args, kwargs = mocked_get.call_args
        self.assertEqual(
            args[0],
            "https://tasks.example.test/api/v1/manager/operational-tasks/",
        )
        self.assertEqual(kwargs["headers"]["Authorization"], f"Bearer {self.TOKEN}")
        self.assertNotIn(self.TOKEN, snapshot.detail)

    @patch("integrations.tasks.httpx.get")
    def test_disabled_integration_does_not_make_network_request(self, mocked_get):
        with self._environment(TASKS_ENABLED="false"):
            snapshot = tasks_snapshot()

        self.assertEqual(snapshot.state, "disabled")
        mocked_get.assert_not_called()

    @patch("integrations.tasks.httpx.get")
    def test_ambiguous_token_configuration_fails_closed(self, mocked_get):
        with self._environment(
            TASKS_ACCESS_TOKEN_FILE="/run/secrets/also-configured",
        ):
            snapshot = tasks_snapshot()

        self.assertEqual(snapshot.state, "misconfigured")
        self.assertIn("only one", snapshot.detail.lower())
        self.assertNotIn(self.TOKEN, snapshot.detail)
        mocked_get.assert_not_called()

    @patch("integrations.tasks.httpx.get")
    def test_timeout_is_unavailable_without_secret_disclosure(self, mocked_get):
        mocked_get.side_effect = httpx.TimeoutException("slow")

        with self._environment():
            snapshot = tasks_snapshot()

        self.assertEqual(snapshot.state, "unavailable")
        self.assertIn("timeout", snapshot.detail)
        self.assertNotIn(self.TOKEN, snapshot.detail)

    @patch("integrations.tasks.httpx.get")
    def test_rejected_credential_is_sanitized(self, mocked_get):
        mocked_get.return_value = self._response(status_code=401, payload={})

        with self._environment():
            snapshot = tasks_snapshot()

        self.assertEqual(snapshot.state, "unavailable")
        self.assertIn("credential", snapshot.detail)
        self.assertNotIn(self.TOKEN, snapshot.detail)

    @patch("integrations.tasks.httpx.get")
    def test_wrong_schema_is_unavailable(self, mocked_get):
        payload = self._payload()
        payload["schema"] = "unexpected.schema"
        mocked_get.return_value = self._response(payload=payload)

        with self._environment():
            snapshot = tasks_snapshot()

        self.assertEqual(snapshot.state, "unavailable")
        self.assertIn("could not safely interpret", snapshot.detail)

    @patch("integrations.tasks.httpx.get")
    def test_inconsistent_counts_are_rejected(self, mocked_get):
        payload = self._payload()
        payload["summary"]["returned"] = 2
        mocked_get.return_value = self._response(payload=payload)

        with self._environment():
            snapshot = tasks_snapshot()

        self.assertEqual(snapshot.state, "unavailable")
        self.assertEqual(snapshot.tasks, ())
