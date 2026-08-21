from pathlib import Path
from unittest import TestCase


WORKFLOW_ROOT = Path(__file__).resolve().parents[1] / ".github" / "workflows"

WORKFLOWS = {
    "runtime-publication-readiness.yml": "bash scripts/validate_runtime_publication_readiness.sh",
    "backup-restore-readiness.yml": "bash scripts/validate_backup_restore_readiness.sh",
    "upgrade-rollback-readiness.yml": "bash scripts/validate_upgrade_rollback_readiness.sh",
    "monitoring-alert-readiness.yml": "bash scripts/validate_monitoring_alert_readiness.sh",
    "production-readiness-evidence-manifest.yml": (
        "python scripts/validate_manager_production_readiness_manifest.py --self-test"
    ),
}

TRIGGER_CONTRACT = """on:\n  push:\n    branches:\n      - main\n  pull_request:\n"""
EXACT_HEAD_CHECKOUT = "ref: ${{ github.event.pull_request.head.sha || github.sha }}"
PINNED_CHECKOUT = (
    "uses: actions/checkout@11d5960a326750d5838078e36cf38b85af677262 # v4"
)


class ReadinessWorkflowTriggerContractTests(TestCase):
    def _workflow(self, name: str) -> str:
        return (WORKFLOW_ROOT / name).read_text(encoding="utf-8")

    def test_readiness_workflows_run_on_main_push_and_pull_request_only(self):
        for name in WORKFLOWS:
            with self.subTest(workflow=name):
                workflow = self._workflow(name)
                self.assertIn(TRIGGER_CONTRACT, workflow)
                self.assertNotIn('"agent/**"', workflow)
                self.assertNotIn("- agent/**", workflow)

    def test_readiness_workflows_preserve_exact_head_checkout(self):
        for name in WORKFLOWS:
            with self.subTest(workflow=name):
                workflow = self._workflow(name)
                self.assertIn(PINNED_CHECKOUT, workflow)
                self.assertIn(EXACT_HEAD_CHECKOUT, workflow)

    def test_readiness_workflows_preserve_validation_commands(self):
        for name, command in WORKFLOWS.items():
            with self.subTest(workflow=name):
                self.assertIn(command, self._workflow(name))

    def test_upgrade_rollback_retains_full_history_checkout(self):
        workflow = self._workflow("upgrade-rollback-readiness.yml")
        self.assertIn("fetch-depth: 0", workflow)
