from __future__ import annotations

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from core.auth_throttle import LOCK_SECONDS, MAX_FAILURES, _account_key
from core.models import LoginThrottleBucket


class SharedLoginThrottleTests(TestCase):
    username = "manager-admin"
    password = "correct-horse-battery-staple-2026"

    def setUp(self):
        get_user_model().objects.create_user(
            username=self.username,
            password=self.password,
        )

    def _login(self, password: str):
        return self.client.post(
            reverse("login"),
            {"username": self.username, "password": password},
        )

    def test_failed_attempts_create_only_pseudonymous_shared_state(self):
        response = self._login("wrong-password")

        self.assertEqual(response.status_code, 200)
        bucket = LoginThrottleBucket.objects.get()
        self.assertEqual(bucket.key, _account_key(self.username))
        self.assertNotIn(self.username, bucket.key)
        self.assertEqual(len(bucket.key), 64)
        self.assertEqual(bucket.failures, 1)

    def test_fifth_failure_locks_correct_credentials_until_expiry(self):
        for _ in range(MAX_FAILURES):
            response = self._login("wrong-password")
            self.assertEqual(response.status_code, 200)

        bucket = LoginThrottleBucket.objects.get()
        self.assertIsNotNone(bucket.locked_until)
        self.assertGreater(bucket.locked_until, timezone.now())

        blocked = self._login(self.password)
        self.assertEqual(blocked.status_code, 200)
        self.assertNotIn("locked", blocked.content.decode("utf-8").lower())
        self.assertNotIn("throttle", blocked.content.decode("utf-8").lower())
        self.assertNotIn("_auth_user_id", self.client.session)

        bucket.locked_until = timezone.now() - timedelta(seconds=1)
        bucket.window_started_at = timezone.now() - timedelta(seconds=LOCK_SECONDS + 1)
        bucket.save(update_fields=("locked_until", "window_started_at", "updated_at"))

        accepted = self._login(self.password)
        self.assertEqual(accepted.status_code, 302)
        self.assertIn("_auth_user_id", self.client.session)
        self.assertFalse(LoginThrottleBucket.objects.exists())

    def test_success_before_threshold_clears_prior_failures(self):
        self._login("wrong-password")
        self.assertTrue(LoginThrottleBucket.objects.exists())

        response = self._login(self.password)

        self.assertEqual(response.status_code, 302)
        self.assertFalse(LoginThrottleBucket.objects.exists())

    def test_admin_login_uses_same_throttle_form(self):
        for _ in range(MAX_FAILURES):
            response = self.client.post(
                reverse("admin:login"),
                {"username": self.username, "password": "wrong-password", "next": "/admin/"},
            )
            self.assertEqual(response.status_code, 200)

        response = self.client.post(
            reverse("admin:login"),
            {"username": self.username, "password": self.password, "next": "/admin/"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)
