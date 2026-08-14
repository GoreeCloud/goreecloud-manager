"""Regression tests for GoreeCloud Manager authentication and session behavior."""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.contrib.sessions.models import Session
from django.test import TestCase
from django.urls import reverse


class AuthenticationSessionResilienceTests(TestCase):
    def setUp(self) -> None:
        self.username = "manager-session-test"
        self.password = "strong-manager-session-test-password"
        self.user = get_user_model().objects.create_user(
            username=self.username,
            password=self.password,
        )

    def test_login_rotates_pre_authentication_session_key(self):
        anonymous_session = self.client.session
        anonymous_session["pre_auth_marker"] = "retained"
        anonymous_session.save()
        previous_key = anonymous_session.session_key

        response = self.client.post(
            reverse("login"),
            {"username": self.username, "password": self.password},
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("overview"))
        authenticated_session = self.client.session
        self.assertNotEqual(authenticated_session.session_key, previous_key)
        self.assertEqual(authenticated_session["pre_auth_marker"], "retained")

    def test_logout_requires_post_and_flushes_server_side_session(self):
        self.assertTrue(self.client.login(username=self.username, password=self.password))
        active_session_key = self.client.session.session_key
        self.assertTrue(Session.objects.filter(session_key=active_session_key).exists())

        get_response = self.client.get(reverse("logout"))
        self.assertEqual(get_response.status_code, 405)
        self.assertEqual(self.client.get(reverse("overview")).status_code, 200)

        post_response = self.client.post(reverse("logout"))
        self.assertEqual(post_response.status_code, 302)
        self.assertEqual(post_response.url, reverse("login"))
        self.assertFalse(Session.objects.filter(session_key=active_session_key).exists())
        self.assertEqual(self.client.get(reverse("overview")).status_code, 302)

    def test_password_change_invalidates_an_existing_session(self):
        self.assertTrue(self.client.login(username=self.username, password=self.password))
        self.assertEqual(self.client.get(reverse("overview")).status_code, 200)

        self.user.set_password("new-strong-manager-session-test-password")
        self.user.save(update_fields=["password"])

        response = self.client.get(reverse("overview"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response.url)

    def test_login_template_preserves_internal_next_destination(self):
        target = reverse("tasks")
        form_response = self.client.get(reverse("login"), {"next": target})
        self.assertEqual(form_response.status_code, 200)
        self.assertContains(form_response, f'name="next" value="{target}"')

        login_response = self.client.post(
            reverse("login"),
            {
                "username": self.username,
                "password": self.password,
                "next": target,
            },
        )
        self.assertEqual(login_response.status_code, 302)
        self.assertEqual(login_response.url, target)

    def test_external_next_destination_is_rejected(self):
        response = self.client.post(
            reverse("login"),
            {
                "username": self.username,
                "password": self.password,
                "next": "https://untrusted.example/collect-session",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("overview"))

    def test_login_page_is_not_cacheable(self):
        response = self.client.get(reverse("login"))

        self.assertEqual(response.status_code, 200)
        cache_control = response.headers.get("Cache-Control", "")
        self.assertIn("no-store", cache_control)
        self.assertIn("no-cache", cache_control)

    def test_failed_login_log_does_not_include_submitted_credentials(self):
        submitted_username = "sensitive-operator-name"
        submitted_password = "sensitive-password-value"

        with self.assertLogs("core.auth", level="WARNING") as captured:
            response = self.client.post(
                reverse("login"),
                {
                    "username": submitted_username,
                    "password": submitted_password,
                },
            )

        self.assertEqual(response.status_code, 200)
        output = "\n".join(captured.output)
        self.assertIn("event=auth_login_failed", output)
        self.assertIn("request_id=", output)
        self.assertNotIn(submitted_username, output)
        self.assertNotIn(submitted_password, output)

    def test_success_and_logout_logs_use_internal_user_id_only(self):
        with self.assertLogs("core.auth", level="INFO") as captured:
            login_response = self.client.post(
                reverse("login"),
                {"username": self.username, "password": self.password},
            )
            logout_response = self.client.post(reverse("logout"))

        self.assertEqual(login_response.status_code, 302)
        self.assertEqual(logout_response.status_code, 302)
        output = "\n".join(captured.output)
        self.assertIn("event=auth_login_succeeded", output)
        self.assertIn("event=auth_logout", output)
        self.assertIn(f"user_id={self.user.pk}", output)
        self.assertNotIn(self.username, output)
        self.assertNotIn(self.password, output)
