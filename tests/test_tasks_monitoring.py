"""Tests for the sanitized GoreeCloud Tasks integration monitoring signal."""

import os
from unittest.mock import patch

import httpx
from django.test import SimpleTestCase

from integrations.tasks import TasksSnapshot, tasks_snapshot


class TasksMonitoringConditionTests(SimpleTestCase):
    TOKEN = "manager-monitor-test-token-0123456789abcdef0123456789abcdef"

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

    def _response(self, status_code=200, payload=None):
        return httpx.Response(
            status_code,
            request=httpx.Request(
                "GET",
                "https://tasks.example.test/api/v1/manager/operational-tasks/",
            ),
            json=payload,
        )

    def _healthy_payload(self):
        return {
            "schema": "goreecloud.tasks.manager.v1",
            "version": 1,
            "generated_at": "2026-08-13T10:00:00-05:00",
            "authorization": {
                "identity": "goreecloud-manager-integration",
                "scope": "visible operational project tasks only",
            },
            "summary": {
                "total_open": 0,
                "blocked": 0,
                "p0": 0,
                "p1": 0,
                "returned": 0,
            },
            "tasks": [],
        }

    @patch("integrations.tasks.httpx.get")
    def test_healthy_condition(self, mocked_get):
        mocked_get.return_value = self._response(payload=self._healthy_payload())

        with self._environment():
            snapshot = tasks_snapshot()

        self.assertEqual(snapshot.state, "healthy")
        self.assertEqual(snapshot.condition, "healthy")
        self.assertEqual(
            snapshot.monitoring_status(),
            {"state": "healthy", "condition": "healthy"},
        )

    @patch("integrations.tasks.httpx.get")
    def test_disabled_condition_does_not_call_tasks(self, mocked_get):
        with self._environment(TASKS_ENABLED="false"):
            snapshot = tasks_snapshot()

        self.assertEqual(snapshot.condition, "disabled")
        mocked_get.assert_not_called()

    @patch("integrations.tasks.httpx.get")
    def test_misconfigured_condition_does_not_call_tasks(self, mocked_get):
        with self._environment(TASKS_ACCESS_TOKEN="", TASKS_ACCESS_TOKEN_FILE=""):
            snapshot = tasks_snapshot()

        self.assertEqual(snapshot.condition, "misconfigured")
        mocked_get.assert_not_called()

    @patch("integrations.tasks.httpx.get")
    def test_unreachable_condition(self, mocked_get):
        mocked_get.side_effect = httpx.ConnectError("unreachable")

        with self._environment():
            snapshot = tasks_snapshot()

        self.assertEqual(snapshot.condition, "unreachable")
        self.assertNotIn(self.TOKEN, snapshot.detail)

    @patch("integrations.tasks.httpx.get")
    def test_authentication_rejected_condition(self, mocked_get):
        mocked_get.return_value = self._response(status_code=401, payload={})

        with self._environment():
            snapshot = tasks_snapshot()

        self.assertEqual(snapshot.condition, "authentication-rejected")
        self.assertNotIn(self.TOKEN, snapshot.detail)

    @patch("integrations.tasks.httpx.get")
    def test_authorization_denied_condition(self, mocked_get):
        mocked_get.return_value = self._response(status_code=403, payload={})

        with self._environment():
            snapshot = tasks_snapshot()

        self.assertEqual(snapshot.condition, "authorization-denied")
        self.assertNotIn(self.TOKEN, snapshot.detail)

    @patch("integrations.tasks.httpx.get")
    def test_endpoint_unavailable_condition(self, mocked_get):
        mocked_get.return_value = self._response(status_code=404, payload={})

        with self._environment():
            snapshot = tasks_snapshot()

        self.assertEqual(snapshot.condition, "endpoint-unavailable")

    @patch("integrations.tasks.httpx.get")
    def test_upstream_error_condition(self, mocked_get):
        mocked_get.return_value = self._response(status_code=500, payload={})

        with self._environment():
            snapshot = tasks_snapshot()

        self.assertEqual(snapshot.condition, "upstream-error")

    @patch("integrations.tasks.httpx.get")
    def test_schema_invalid_condition(self, mocked_get):
        payload = self._healthy_payload()
        payload["version"] = 999
        mocked_get.return_value = self._response(payload=payload)

        with self._environment():
            snapshot = tasks_snapshot()

        self.assertEqual(snapshot.condition, "schema-invalid")


class TasksMonitoringEndpointTests(SimpleTestCase):
    PATH = "/healthz/integrations/tasks/"

    @patch("core.views.tasks_snapshot")
    def test_healthy_endpoint_is_minimal_and_uncached(self, mocked_snapshot):
        mocked_snapshot.return_value = TasksSnapshot(
            state="healthy",
            detail="PRIVATE-DETAIL-MUST-NOT-LEAK",
            condition="healthy",
            total_open=27,
            identity="private-integration-identity",
        )

        response = self.client.get(self.PATH)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "status": "ok",
                "service": "goreecloud-manager",
                "integration": "goreecloud-tasks",
                "state": "healthy",
                "condition": "healthy",
            },
        )
        self.assertEqual(response.headers["Cache-Control"], "no-store")
        body = response.content.decode("utf-8")
        self.assertNotIn("PRIVATE-DETAIL-MUST-NOT-LEAK", body)
        self.assertNotIn("private-integration-identity", body)
        self.assertNotIn("27", body)

    @patch("core.views.tasks_snapshot")
    def test_nonhealthy_conditions_return_503_without_private_context(self, mocked_snapshot):
        conditions = (
            ("disabled", "disabled"),
            ("misconfigured", "misconfigured"),
            ("unavailable", "unreachable"),
            ("unavailable", "authentication-rejected"),
            ("unavailable", "authorization-denied"),
            ("unavailable", "endpoint-unavailable"),
            ("unavailable", "upstream-error"),
            ("unavailable", "schema-invalid"),
        )

        for state, condition in conditions:
            with self.subTest(condition=condition):
                mocked_snapshot.return_value = TasksSnapshot(
                    state=state,
                    detail="PRIVATE-TASK-OR-CREDENTIAL-CONTEXT-MUST-NOT-LEAK",
                    condition=condition,
                    total_open=99,
                    identity="private-integration-identity",
                )
                response = self.client.get(self.PATH)

                self.assertEqual(response.status_code, 503)
                self.assertEqual(response.json()["status"], "unhealthy")
                self.assertEqual(response.json()["state"], state)
                self.assertEqual(response.json()["condition"], condition)
                body = response.content.decode("utf-8")
                self.assertNotIn("PRIVATE-TASK-OR-CREDENTIAL-CONTEXT-MUST-NOT-LEAK", body)
                self.assertNotIn("private-integration-identity", body)
                self.assertNotIn("99", body)

    @patch("core.views.tasks_snapshot")
    def test_monitoring_endpoint_is_get_only(self, mocked_snapshot):
        response = self.client.post(self.PATH, data={})

        self.assertEqual(response.status_code, 405)
        mocked_snapshot.assert_not_called()

    @patch("core.views.tasks_snapshot")
    def test_generic_healthz_remains_independent(self, mocked_snapshot):
        response = self.client.get("/healthz/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok", "service": "goreecloud-manager"})
        mocked_snapshot.assert_not_called()
