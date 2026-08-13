"""Regression tests for the shared GoreeCloud Manager application shell."""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse


class ManagerShellTests(TestCase):
    def test_login_exposes_accessible_glaze_ui_shell(self):
        response = self.client.get(reverse("login"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Skip to main content")
        self.assertContains(response, "data-theme-toggle")
        self.assertContains(response, "Authenticated access is required")
        self.assertContains(response, 'id="main-content"')

    def test_overview_marks_active_navigation(self):
        user = get_user_model().objects.create_user(username="ui-shell-admin")
        self.client.force_login(user)
        response = self.client.get(reverse("overview"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'aria-label="Primary"')
        self.assertContains(response, 'aria-current="page"', count=1)
        self.assertContains(response, "data-theme-toggle")

    def test_tasks_marks_tasks_navigation_as_current(self):
        user = get_user_model().objects.create_user(username="ui-shell-tasks-admin")
        self.client.force_login(user)
        response = self.client.get(reverse("tasks"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'href="/tasks/" aria-current="page"')
