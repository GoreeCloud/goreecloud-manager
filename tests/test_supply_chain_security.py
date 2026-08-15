"""Supply-chain SBOM and vulnerability-evidence regression tests."""

from __future__ import annotations

import datetime as dt
import importlib.util
import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPOSITORY_ROOT / "scripts" / "python_supply_chain_security.py"
spec = importlib.util.spec_from_file_location("manager_supply_chain_security", SCRIPT_PATH)
if spec is None or spec.loader is None:  # pragma: no cover
    raise RuntimeError("Unable to load supply-chain security script")
security = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = security
spec.loader.exec_module(security)


class PythonSupplyChainSecurityTests(TestCase):
    def setUp(self):
        self.lock_path = REPOSITORY_ROOT / "requirements.lock"
        self.packages = security.parse_lock(self.lock_path)

    def test_lock_and_sbom_cover_exact_python_runtime_graph(self):
        self.assertEqual(len(self.packages), 12)
        versions = {package.normalized_name: package.version for package in self.packages}
        self.assertEqual(versions["django"], "5.2.17")
        self.assertEqual(versions["gunicorn"], "26.0.0")
        self.assertEqual(versions["httpx"], "0.28.1")
        self.assertEqual(versions["whitenoise"], "6.12.0")

        digest = security.lock_sha256(self.lock_path)
        first = security.build_sbom(self.packages, "0123456789abcdef", digest)
        second = security.build_sbom(self.packages, "0123456789abcdef", digest)
        self.assertEqual(first, second)
        self.assertEqual(first["bomFormat"], "CycloneDX")
        self.assertEqual(first["specVersion"], "1.7")
        self.assertEqual(len(first["components"]), 12)
        properties = {
            item["name"]: item["value"] for item in first["metadata"]["properties"]
        }
        self.assertEqual(properties["goreecloud:python-lock-sha256"], digest)
        self.assertEqual(properties["goreecloud:sbom-scope"], "python-runtime-dependencies")
        for package, component in zip(self.packages, first["components"], strict=True):
            self.assertEqual(component["purl"], package.purl)
            self.assertEqual(component["hashes"], [{"alg": "SHA-256", "content": package.sha256}])

    @patch.object(security, "post_osv")
    def test_osv_query_maps_findings_to_locked_package(self, post_osv):
        post_osv.return_value = {
            "results": [
                {
                    "vulns": [
                        {
                            "id": "GHSA-example-0000-0000",
                            "modified": "2026-08-15T00:00:00Z",
                        }
                    ]
                },
                *({} for _ in self.packages[1:]),
            ]
        }
        findings = security.query_osv(self.packages)
        self.assertEqual(
            findings,
            [
                {
                    "package": "django",
                    "version": "5.2.17",
                    "osv_id": "GHSA-example-0000-0000",
                    "modified": "2026-08-15T00:00:00Z",
                }
            ],
        )
        payload = post_osv.call_args.args[0]
        self.assertEqual(len(payload["queries"]), 12)
        self.assertEqual(payload["queries"][0]["package"]["ecosystem"], "PyPI")

    def test_unexcepted_finding_blocks_and_exact_unexpired_exception_can_waive(self):
        findings = [
            {
                "package": "django",
                "version": "5.2.17",
                "osv_id": "GHSA-example-0000-0000",
                "modified": "2026-08-15T00:00:00Z",
            }
        ]
        policy = {
            "schema_version": 1,
            "policy": {"fail_on_any_known_vulnerability": True},
            "exceptions": [],
        }
        allowed, blocking = security.classify(findings, policy, dt.date(2026, 8, 15))
        self.assertEqual(allowed, [])
        self.assertEqual(blocking, findings)

        policy["exceptions"] = [
            {
                "osv_id": "GHSA-example-0000-0000",
                "package": "Django",
                "expires_on": "2026-08-20",
                "reason": "Synthetic regression-only waiver.",
            }
        ]
        allowed, blocking = security.classify(findings, policy, dt.date(2026, 8, 15))
        self.assertEqual(blocking, [])
        self.assertEqual(allowed[0]["exception_expires_on"], "2026-08-20")
        self.assertEqual(allowed[0]["exception_reason"], "Synthetic regression-only waiver.")

        policy["exceptions"][0]["package"] = "gunicorn"
        allowed, blocking = security.classify(findings, policy, dt.date(2026, 8, 15))
        self.assertEqual(allowed, [])
        self.assertEqual(blocking, findings)

    def test_expired_exception_fails_closed(self):
        policy = {
            "schema_version": 1,
            "policy": {"fail_on_any_known_vulnerability": True},
            "exceptions": [
                {
                    "osv_id": "GHSA-example-0000-0000",
                    "package": "django",
                    "expires_on": "2026-08-14",
                    "reason": "Expired synthetic waiver.",
                }
            ],
        }
        with self.assertRaisesRegex(ValueError, "Expired OSV exception"):
            security.classify([], policy, dt.date(2026, 8, 15))

    @patch.object(security, "query_osv", side_effect=RuntimeError("secret detail"))
    def test_scanner_error_report_is_sanitized_and_fails_closed(self, _query):
        with TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "osv-report.json"
            policy = Path(temp_dir) / "policy.json"
            policy.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "policy": {"fail_on_any_known_vulnerability": True},
                        "exceptions": [],
                    }
                ),
                encoding="utf-8",
            )
            exit_code = security.command_scan(
                SimpleNamespace(
                    lock=str(self.lock_path),
                    policy=str(policy),
                    output=str(output),
                    source_revision="deadbeef",
                    timeout_seconds=1.0,
                    attempts=1,
                )
            )
            report = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(exit_code, 2)
        self.assertEqual(report["status"], "error")
        self.assertEqual(report["error_type"], "RuntimeError")
        self.assertNotIn("secret detail", json.dumps(report))

    def test_ci_retains_and_enforces_machine_readable_security_evidence(self):
        workflow = (
            REPOSITORY_ROOT / ".github" / "workflows" / "ci.yml"
        ).read_text(encoding="utf-8")
        self.assertIn("python_supply_chain_security.py sbom", workflow)
        self.assertIn("python_supply_chain_security.py scan", workflow)
        self.assertIn("security/osv-policy.json", workflow)
        self.assertIn("id: osv_scan", workflow)
        self.assertIn("continue-on-error: true", workflow)
        self.assertIn("steps.osv_scan.outcome", workflow)
        self.assertIn("security-artifacts/goreecloud-manager-python.cdx.json", workflow)
        self.assertIn("security-artifacts/osv-python-vulnerabilities.json", workflow)
        self.assertIn(
            "actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02",
            workflow,
        )
        self.assertIn("if: always()", workflow)
        self.assertIn("retention-days: 30", workflow)
        self.assertIn("if-no-files-found: error", workflow)
