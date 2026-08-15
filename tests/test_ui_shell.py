"""Regression tests for the shared GoreeCloud Manager application shell."""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse


class ManagerShellTests(TestCase):
    def test_login_exposes_accessible_private_glaze_ui_shell(self):
        response = self.client.get(reverse("login"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Skip to main content")
        self.assertContains(response, "data-theme-toggle")
        self.assertContains(response, "Authenticated access is required")
        self.assertContains(response, 'id="main-content" tabindex="-1"')
        self.assertContains(response, 'data-glaze-ui="manager"')
        self.assertContains(response, 'content="noindex, nofollow, noarchive"')
        self.assertContains(response, 'name="referrer" content="same-origin"')
        # Production static storage fingerprints local assets, so rendered-shell
        # assertions verify stable asset identity rather than an unhashed URL.
        self.assertContains(response, "manager-mark")
        self.assertContains(response, ".svg")
        self.assertContains(response, "glaze-ui")
        self.assertContains(response, ".css")

    def test_overview_marks_active_navigation_and_goreecloud_identity(self):
        user = get_user_model().objects.create_user(username="ui-shell-admin")
        self.client.force_login(user)
        response = self.client.get(reverse("overview"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'aria-label="Primary"')
        self.assertContains(response, 'aria-current="page"', count=1)
        self.assertContains(response, "data-theme-toggle")
        self.assertContains(response, 'class="brand-symbol"')
        self.assertContains(response, "GoreeCloud")
        self.assertContains(response, "Manager")

    def test_tasks_marks_tasks_navigation_as_current(self):
        user = get_user_model().objects.create_user(username="ui-shell-tasks-admin")
        self.client.force_login(user)
        response = self.client.get(reverse("tasks"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'href="/tasks/" aria-current="page"')
        self.assertContains(response, 'data-glaze-ui="manager"')
