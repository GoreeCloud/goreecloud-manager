"""View tests for GoreeCloud Tasks visibility in Manager."""

from datetime import UTC, datetime
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from integrations.tasks import ManagerTask, TasksSnapshot


class TasksViewTests(TestCase):
    def test_tasks_page_requires_authentication(self):
        response = self.client.get(reverse("tasks"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response.url)

    @patch("core.views.tasks_snapshot")
    def test_tasks_page_renders_authorization_scoped_operational_work(
        self, mocked_snapshot
    ):
        mocked_snapshot.return_value = TasksSnapshot(
            state="healthy",
            detail="Live authorization-scoped Tasks API data verified for 1 open operational task(s).",
            tasks=(
                ManagerTask(
                    task_id=42,
                    title="Validate backup recovery path",
                    project_id=7,
                    project_name="Infrastructure Work",
                    priority=1,
                    priority_label="P1 — Urgent",
                    status="blocked",
                    status_label="Blocked",
                    due_at=datetime(2026, 8, 13, 14, 0, tzinfo=UTC),
                    assigned_system="Infrastructure Services VM",
                    assigned_service="Kopia",
                    environment="production-planning",
                    workload_category="Recovery",
                    blocker="Restore test not yet completed",
                    resume_condition="Complete isolated restore validation",
                    backup_required=True,
                    recovery_required=True,
                    validation_required=True,
                    documentation_required=True,
                    related_change_record="GoreeCloud Tasks change log",
                    related_documentation="Backup and recovery standard",
                    updated_at=datetime(2026, 8, 12, 16, 15, tzinfo=UTC),
                ),
            ),
            total_open=1,
            blocked=1,
            p0=0,
            p1=1,
            identity="goreecloud-manager-integration",
            observed_at=datetime(2026, 8, 12, 16, 20, tzinfo=UTC),
        )
        user = get_user_model().objects.create_user(
            username="tasks-manager-view-test",
            password="strong-test-password",
        )
        self.client.force_login(user)

        response = self.client.get(reverse("tasks"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "GoreeCloud Tasks")
        self.assertContains(response, "Validate backup recovery path")
        self.assertContains(response, "Infrastructure Work")
        self.assertContains(response, "Kopia")
        self.assertContains(response, "Restore test not yet completed")
        self.assertContains(response, "goreecloud-manager-integration")
        self.assertContains(response, "Aug 13, 2026 9:00 AM CDT")
        self.assertContains(response, "Read only")

    @patch("core.views.tasks_snapshot")
    def test_tasks_page_renders_fail_soft_integration_state(self, mocked_snapshot):
        mocked_snapshot.return_value = TasksSnapshot(
            state="unavailable",
            detail="GoreeCloud Tasks did not respond before the configured timeout.",
        )
        user = get_user_model().objects.create_user(
            username="tasks-manager-unavailable-test",
            password="strong-test-password",
        )
        self.client.force_login(user)

        response = self.client.get(reverse("tasks"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Live task data is not available")
        self.assertContains(response, "configured timeout")
