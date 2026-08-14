"""Regression tests for GoreeCloud Manager production security settings."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

from django.test import SimpleTestCase

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


class ProductionSecuritySettingsTests(SimpleTestCase):
    """Validate settings behavior in isolated interpreter processes."""

    @staticmethod
    def _run_settings(*, debug: str, direct_secret: str = "", secret_file: str = ""):
        env = os.environ.copy()
        env.pop("DJANGO_SECRET_KEY", None)
        env.pop("DJANGO_SECRET_KEY_FILE", None)
        env["DJANGO_DEBUG"] = debug
        if direct_secret:
            env["DJANGO_SECRET_KEY"] = direct_secret
        if secret_file:
            env["DJANGO_SECRET_KEY_FILE"] = secret_file
        return subprocess.run(
            [
                sys.executable,
                "-c",
                (
                    "import goreecloud_manager.settings as s; "
                    "print(s.SESSION_COOKIE_SECURE); "
                    "print(s.CSRF_COOKIE_SECURE); "
                    "print(s.SECURE_PROXY_SSL_HEADER); "
                    "print(s.SECRET_KEY == 'synthetic-file-secret-for-tests')"
                ),
            ],
            cwd=REPOSITORY_ROOT,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )

    def test_production_mode_rejects_development_default_secret(self):
        result = self._run_settings(debug="false")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("non-development secret", result.stderr)
        self.assertNotIn("unsafe-development-key-change-me", result.stderr)

    def test_file_backed_secret_enables_production_security_controls(self):
        with tempfile.NamedTemporaryFile("w", encoding="utf-8") as handle:
            handle.write("synthetic-file-secret-for-tests")
            handle.flush()
            result = self._run_settings(debug="false", secret_file=handle.name)

        self.assertEqual(result.returncode, 0, result.stderr)
        lines = result.stdout.strip().splitlines()
        self.assertEqual(lines, ["True", "True", "('HTTP_X_FORWARDED_PROTO', 'https')", "True"])

    def test_direct_and_file_secret_sources_are_mutually_exclusive(self):
        with tempfile.NamedTemporaryFile("w", encoding="utf-8") as handle:
            handle.write("synthetic-file-secret-for-tests")
            handle.flush()
            result = self._run_settings(
                debug="false",
                direct_secret="synthetic-direct-secret-for-tests",
                secret_file=handle.name,
            )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Set only one of DJANGO_SECRET_KEY or DJANGO_SECRET_KEY_FILE", result.stderr)
        self.assertNotIn("synthetic-direct-secret-for-tests", result.stderr)
        self.assertNotIn("synthetic-file-secret-for-tests", result.stderr)

    def test_debug_mode_can_use_development_default_without_secure_cookies(self):
        result = self._run_settings(debug="true")
        self.assertEqual(result.returncode, 0, result.stderr)
        lines = result.stdout.strip().splitlines()
        self.assertEqual(lines[:3], ["False", "False", "('HTTP_X_FORWARDED_PROTO', 'https')"])
