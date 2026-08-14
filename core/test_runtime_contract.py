"""Regression checks for source-controlled runtime and CI contracts."""

from pathlib import Path

from django.test import SimpleTestCase


REPOSITORY_ROOT = Path(__file__).resolve().parent.parent


class RuntimeContractTests(SimpleTestCase):
    def test_compose_uses_source_controlled_gunicorn_configuration(self):
        compose = (REPOSITORY_ROOT / "compose.yml").read_text(encoding="utf-8")

        self.assertIn(
            "exec gunicorn -c gunicorn.conf.py goreecloud_manager.wsgi:application",
            compose,
        )
        self.assertNotIn("--workers 2 --access-logfile - --error-logfile -", compose)

    def test_ci_uses_explicit_manager_runtime_baseline(self):
        workflow = (
            REPOSITORY_ROOT / ".github" / "workflows" / "ci.yml"
        ).read_text(encoding="utf-8")

        self.assertIn("runs-on: ubuntu-24.04", workflow)
        self.assertIn('python-version: "3.14.6"', workflow)
        self.assertIn("timeout-minutes: 15", workflow)
        self.assertIn("python -m pip check", workflow)
