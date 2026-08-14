"""Operational stability regression tests for GoreeCloud Manager."""

from __future__ import annotations

import os
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

    def test_container_health_contract_uses_readiness_endpoint(self):
        compose = (REPOSITORY_ROOT / "compose.yml").read_text(encoding="utf-8")
        dockerfile = (REPOSITORY_ROOT / "Dockerfile").read_text(encoding="utf-8")

        self.assertIn("http://127.0.0.1:8000/readyz/", compose)
        self.assertIn("http://127.0.0.1:8000/readyz/", dockerfile)
