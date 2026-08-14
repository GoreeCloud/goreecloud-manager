"""Regression tests for GoreeCloud Manager session configuration bounds."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from django.test import SimpleTestCase

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


class SessionSettingsTests(SimpleTestCase):
    @staticmethod
    def _run_settings(extra_env: dict[str, str] | None = None):
        env = os.environ.copy()
        env["DJANGO_DEBUG"] = "true"
        env.pop("DJANGO_SECRET_KEY", None)
        env.pop("DJANGO_SECRET_KEY_FILE", None)
        env.pop("DJANGO_SESSION_COOKIE_AGE_SECONDS", None)
        env.pop("DJANGO_SESSION_EXPIRE_AT_BROWSER_CLOSE", None)
        if extra_env:
            env.update(extra_env)

        return subprocess.run(
            [
                sys.executable,
                "-c",
                (
                    "import goreecloud_manager.settings as s; "
                    "print(s.SESSION_ENGINE); "
                    "print(s.SESSION_COOKIE_NAME); "
                    "print(s.SESSION_COOKIE_AGE); "
                    "print(s.SESSION_EXPIRE_AT_BROWSER_CLOSE); "
                    "print(s.SESSION_SAVE_EVERY_REQUEST); "
                    "print(s.SESSION_COOKIE_HTTPONLY); "
                    "print(s.CSRF_COOKIE_NAME); "
                    "print(s.CSRF_COOKIE_HTTPONLY)"
                ),
            ],
            cwd=REPOSITORY_ROOT,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )

    def test_session_defaults_are_bounded_and_server_side(self):
        result = self._run_settings()

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            result.stdout.strip().splitlines(),
            [
                "django.contrib.sessions.backends.db",
                "goreecloud_manager_sessionid",
                "28800",
                "True",
                "False",
                "True",
                "goreecloud_manager_csrftoken",
                "True",
            ],
        )

    def test_session_age_and_browser_close_behavior_can_be_tightened(self):
        result = self._run_settings(
            {
                "DJANGO_SESSION_COOKIE_AGE_SECONDS": "3600",
                "DJANGO_SESSION_EXPIRE_AT_BROWSER_CLOSE": "false",
            }
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        lines = result.stdout.strip().splitlines()
        self.assertEqual(lines[2:5], ["3600", "False", "False"])

    def test_session_age_rejects_values_below_fifteen_minutes(self):
        result = self._run_settings({"DJANGO_SESSION_COOKIE_AGE_SECONDS": "899"})

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("must be at least 900 seconds", result.stderr)

    def test_session_age_rejects_values_above_twenty_four_hours(self):
        result = self._run_settings({"DJANGO_SESSION_COOKIE_AGE_SECONDS": "86401"})

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("must be no greater than 86400 seconds", result.stderr)

    def test_session_age_rejects_non_integer_input(self):
        result = self._run_settings({"DJANGO_SESSION_COOKIE_AGE_SECONDS": "eight-hours"})

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("must be an integer", result.stderr)
