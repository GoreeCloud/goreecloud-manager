"""Operational stability regression tests for GoreeCloud Manager."""

from __future__ import annotations

import os
import runpy
from pathlib import Path
from unittest.mock import patch

from django.core.exceptions import ImproperlyConfigured
from django.db.utils import DatabaseError
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from goreecloud_manager import settings

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


class OperationalHealthTests(TestCase):
    def test_liveness_is_public_minimal_non_cached_and_safe_method_only(self):
        response = self.client.get(reverse("healthz"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {"status": "ok", "service": "goreecloud-manager"},
        )
        self.assertEqual(response["Cache-Control"], "no-store")
        self.assertEqual(self.client.post(reverse("healthz")).status_code, 405)

    def test_readiness_is_public_minimal_and_database_aware(self):
        response = self.client.get(reverse("readyz"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {"status": "ready", "service": "goreecloud-manager"},
        )
        self.assertEqual(response["Cache-Control"], "no-store")
        self.assertEqual(self.client.post(reverse("readyz")).status_code, 405)

    @patch("core.views.connections")
    def test_readiness_fails_closed_without_exposing_database_error(
        self, mocked_connections
    ):
        mocked_connections.__getitem__.return_value.cursor.side_effect = DatabaseError(
            "synthetic database path and detail must not escape"
        )

        response = self.client.get(reverse("readyz"))

        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            response.json(),
            {"status": "unavailable", "service": "goreecloud-manager"},
        )
        self.assertNotIn("synthetic", response.content.decode())
        self.assertEqual(response["Cache-Control"], "no-store")


class RuntimeConfigurationTests(SimpleTestCase):
    def test_hsts_seconds_parser_accepts_non_negative_integer(self):
        with patch.dict(
            os.environ,
            {"DJANGO_SECURE_HSTS_SECONDS": "31536000"},
            clear=False,
        ):
            self.assertEqual(
                settings.env_non_negative_int("DJANGO_SECURE_HSTS_SECONDS"),
                31536000,
            )

    def test_hsts_seconds_parser_rejects_invalid_or_negative_input(self):
        for value in ("not-a-number", "-1"):
            with self.subTest(value=value):
                with patch.dict(
                    os.environ,
                    {"DJANGO_SECURE_HSTS_SECONDS": value},
                    clear=False,
                ):
                    with self.assertRaises(ImproperlyConfigured):
                        settings.env_non_negative_int("DJANGO_SECURE_HSTS_SECONDS")

    def test_integration_budget_parser_accepts_safe_positive_value(self):
        with patch.dict(
            os.environ,
            {"MANAGER_INTEGRATION_BUDGET_SECONDS": "7.5"},
            clear=False,
        ):
            self.assertEqual(
                settings.env_positive_float(
                    "MANAGER_INTEGRATION_BUDGET_SECONDS",
                    7.0,
                    maximum=20.0,
                ),
                7.5,
            )

    def test_integration_budget_parser_rejects_invalid_or_unsafe_value(self):
        for value in ("not-a-number", "0", "-1", "21"):
            with self.subTest(value=value):
                with patch.dict(
                    os.environ,
                    {"MANAGER_INTEGRATION_BUDGET_SECONDS": value},
                    clear=False,
                ):
                    with self.assertRaises(ImproperlyConfigured):
                        settings.env_positive_float(
                            "MANAGER_INTEGRATION_BUDGET_SECONDS",
                            7.0,
                            maximum=20.0,
                        )

    def test_container_health_contract_uses_readiness_endpoint(self):
        compose = (REPOSITORY_ROOT / "compose.yml").read_text(encoding="utf-8")
        dockerfile = (REPOSITORY_ROOT / "Dockerfile").read_text(encoding="utf-8")

        self.assertIn("http://127.0.0.1:8000/readyz/", compose)
        self.assertIn("http://127.0.0.1:8000/readyz/", dockerfile)

    def test_gunicorn_runtime_contract_is_bounded_and_query_safe(self):
        config = runpy.run_path(str(REPOSITORY_ROOT / "gunicorn.conf.py"))
        dockerfile = (REPOSITORY_ROOT / "Dockerfile").read_text(encoding="utf-8")

        self.assertEqual(config["workers"], 2)
        self.assertEqual(config["worker_class"], "sync")
        self.assertEqual(config["timeout"], 30)
        self.assertEqual(config["graceful_timeout"], 30)
        self.assertEqual(config["max_requests"], 1000)
        self.assertGreater(config["max_requests_jitter"], 0)
        access_format = config["access_log_format"]
        self.assertIn("%({x-request-id}o)s", access_format)
        self.assertIn("%(U)s", access_format)
        self.assertNotIn("%(q)s", access_format)
        self.assertNotIn("%(r)s", access_format)
        self.assertNotIn("remote", access_format.casefold())
        self.assertIn('"-c", "gunicorn.conf.py"', dockerfile)
