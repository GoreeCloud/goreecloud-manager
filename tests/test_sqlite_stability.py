"""SQLite configuration regression tests for GoreeCloud Manager."""

from __future__ import annotations

import os
from unittest.mock import patch

from django.core.exceptions import ImproperlyConfigured
from django.db import connection
from django.test import SimpleTestCase, TestCase

from goreecloud_manager import settings


class SQLiteConfigurationTests(SimpleTestCase):
    def test_sqlite_contract_is_bounded_and_short_lived(self):
        database = settings.DATABASES["default"]

        self.assertEqual(database["ENGINE"], "django.db.backends.sqlite3")
        self.assertFalse(database["ATOMIC_REQUESTS"])
        self.assertEqual(database["CONN_MAX_AGE"], 0)
        self.assertEqual(database["OPTIONS"]["timeout"], 10.0)
        self.assertEqual(database["OPTIONS"]["transaction_mode"], "IMMEDIATE")

    def test_sqlite_timeout_parser_accepts_safe_positive_value(self):
        with patch.dict(
            os.environ,
            {"DJANGO_SQLITE_TIMEOUT_SECONDS": "12.5"},
            clear=False,
        ):
            self.assertEqual(
                settings.env_positive_float(
                    "DJANGO_SQLITE_TIMEOUT_SECONDS",
                    10.0,
                    maximum=20.0,
                ),
                12.5,
            )

    def test_sqlite_timeout_parser_rejects_invalid_or_unsafe_value(self):
        for value in ("not-a-number", "0", "-1", "21", "nan", "inf", "-inf"):
            with self.subTest(value=value):
                with patch.dict(
                    os.environ,
                    {"DJANGO_SQLITE_TIMEOUT_SECONDS": value},
                    clear=False,
                ):
                    with self.assertRaises(ImproperlyConfigured):
                        settings.env_positive_float(
                            "DJANGO_SQLITE_TIMEOUT_SECONDS",
                            10.0,
                            maximum=20.0,
                        )


class SQLiteConnectionTests(TestCase):
    def test_live_connection_applies_busy_timeout(self):
        with connection.cursor() as cursor:
            cursor.execute("PRAGMA busy_timeout")
            busy_timeout_ms = cursor.fetchone()[0]

        self.assertEqual(busy_timeout_ms, 10000)
