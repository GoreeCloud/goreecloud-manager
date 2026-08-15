"""Container-image SBOM and operating-system vulnerability evidence tests."""

from __future__ import annotations

import datetime as dt
import importlib.util
import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest import TestCase

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPOSITORY_ROOT / "scripts" / "container_supply_chain_security.py"
spec = importlib.util.spec_from_file_location("manager_container_security", SCRIPT_PATH)
if spec is None or spec.loader is None:  # pragma: no cover
    raise RuntimeError("Unable to load container supply-chain security script")
security = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = security
spec.loader.exec_module(security)


def synthetic_report(*vulnerabilities: dict[str, str]) -> dict:
    return {
        "SchemaVersion": 2,
        "ArtifactName": "goreecloud-manager-security:test",
        "ArtifactType": "container_image",
        "Results": [
            {
                "Target": "goreecloud-manager-security:test (debian 13.1)",
                "Class": "os-pkgs",
                "Type": "debian",
                "Vulnerabilities": list(vulnerabilities),
            }
        ],
    }


def vulnerability(
    vulnerability_id: str,
    package: str,
    severity: str,
    *,
    fixed_version: str = "",
    status: str = "affected",
) -> dict[str, str]:
    return {
        "VulnerabilityID": vulnerability_id,
        "PkgName": package,
        "InstalledVersion": "1.0",
        "FixedVersion": fixed_version,
        "Status": status,
        "Severity": severity,
        "SeveritySource": "debian",
    }


class ContainerSupplyChainSecurityTests(TestCase):
    def test_source_revision_requires_full_git_sha(self):
        revision = "a" * 40
        self.assertEqual(security.validate_source_revision(revision), revision)
        with self.assertRaisesRegex(ValueError, "40-character"):
            security.validate_source_revision("deadbeef")

    def test_base_image_contract_extracts_exact_digest(self):
        with TemporaryDirectory() as temp_dir:
            dockerfile = Path(temp_dir) / "Dockerfile"
            dockerfile.write_text(
                "FROM python:3.14.6-slim@sha256:" + ("a" * 64) + "\n",
                encoding="utf-8",
            )
            parsed = security.parse_base_image(dockerfile)
        self.assertEqual(parsed["python_version"], "3.14.6")
        self.assertEqual(parsed["digest"], "a" * 64)
        self.assertEqual(
            parsed["reference"],
            "python:3.14.6-slim@sha256:" + ("a" * 64),
        )

    def test_high_and_critical_findings_block_even_when_unfixed(self):
        with TemporaryDirectory() as temp_dir:
            report_path = Path(temp_dir) / "trivy.json"
            report_path.write_text(
                json.dumps(
                    synthetic_report(
                        vulnerability(
                            "CVE-2026-0001",
                            "openssl",
                            "HIGH",
                            fixed_version="1.1",
                            status="fixed",
                        ),
                        vulnerability(
                            "CVE-2026-0002",
                            "glibc",
                            "CRITICAL",
                            fixed_version="",
                            status="affected",
                        ),
                        vulnerability(
                            "CVE-2026-0003",
                            "zlib",
                            "MEDIUM",
                            fixed_version="1.1",
                            status="fixed",
                        ),
                    )
                ),
                encoding="utf-8",
            )
            _raw, findings, count = security.parse_trivy_report(report_path)

        policy = {
            "schema_version": 1,
            "policy": {
                "blocking_severities": ["HIGH", "CRITICAL"],
                "require_os_package_result": True,
            },
            "exceptions": [],
        }
        allowed, blocking, informational = security.classify(
            findings, policy, dt.date(2026, 8, 15)
        )
        self.assertEqual(count, 1)
        self.assertEqual(allowed, [])
        self.assertEqual(
            {item["vulnerability_id"] for item in blocking},
            {"CVE-2026-0001", "CVE-2026-0002"},
        )
        self.assertEqual(
            [item["vulnerability_id"] for item in informational],
            ["CVE-2026-0003"],
        )

    def test_exact_unexpired_exception_allows_only_matching_package_and_id(self):
        finding = {
            "vulnerability_id": "CVE-2026-0001",
            "package": "openssl",
            "installed_version": "1.0",
            "fixed_version": "",
            "status": "affected",
            "severity": "HIGH",
            "severity_source": "debian",
            "distro": "debian",
        }
        policy = {
            "schema_version": 1,
            "policy": {
                "blocking_severities": ["HIGH", "CRITICAL"],
                "require_os_package_result": True,
            },
            "exceptions": [
                {
                    "vulnerability_id": "CVE-2026-0001",
                    "package": "OpenSSL",
                    "expires_on": "2026-08-20",
                    "reason": "Synthetic regression-only exception.",
                }
            ],
        }
        allowed, blocking, informational = security.classify(
            [finding], policy, dt.date(2026, 8, 15)
        )
        self.assertEqual(blocking, [])
        self.assertEqual(informational, [])
        self.assertEqual(allowed[0]["exception_expires_on"], "2026-08-20")

        policy["exceptions"][0]["package"] = "glibc"
        allowed, blocking, informational = security.classify(
            [finding], policy, dt.date(2026, 8, 15)
        )
        self.assertEqual(allowed, [])
        self.assertEqual(blocking, [finding])
        self.assertEqual(informational, [])

    def test_expired_exception_fails_closed(self):
        policy = {
            "schema_version": 1,
            "policy": {
                "blocking_severities": ["HIGH", "CRITICAL"],
                "require_os_package_result": True,
            },
            "exceptions": [
                {
                    "vulnerability_id": "CVE-2026-0001",
                    "package": "openssl",
                    "expires_on": "2026-08-14",
                    "reason": "Expired synthetic exception.",
                }
            ],
        }
        with self.assertRaisesRegex(ValueError, "Expired container vulnerability exception"):
            security.classify([], policy, dt.date(2026, 8, 15))

    def test_report_without_os_package_result_fails_closed(self):
        with TemporaryDirectory() as temp_dir:
            report_path = Path(temp_dir) / "trivy.json"
            report_path.write_text(
                json.dumps(
                    {
                        "SchemaVersion": 2,
                        "Results": [
                            {
                                "Target": "Python",
                                "Class": "lang-pkgs",
                                "Type": "python-pkg",
                                "Vulnerabilities": [],
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "OS package result"):
                security.parse_trivy_report(report_path)

    def test_cyclonedx_sbom_is_stamped_with_exact_source_and_image_identity(self):
        with TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            source = temp / "source.cdx.json"
            output = temp / "output.cdx.json"
            source.write_text(
                json.dumps(
                    {
                        "bomFormat": "CycloneDX",
                        "specVersion": "1.6",
                        "metadata": {},
                        "components": [],
                    }
                ),
                encoding="utf-8",
            )
            security.stamp_sbom(
                source,
                output,
                source_revision="a" * 40,
                image_reference="goreecloud-manager-security:" + ("a" * 40),
                image_id="sha256:" + ("b" * 64),
                scanner_version="0.74.0",
                base_image={
                    "reference": "python:3.14.6-slim@sha256:" + ("c" * 64),
                    "python_version": "3.14.6",
                    "digest": "c" * 64,
                },
            )
            payload = json.loads(output.read_text(encoding="utf-8"))

        properties = {
            item["name"]: item["value"]
            for item in payload["metadata"]["properties"]
        }
        self.assertEqual(properties["goreecloud:source-revision"], "a" * 40)
        self.assertEqual(properties["goreecloud:sbom-scope"], "built-container-image")
        self.assertEqual(properties["goreecloud:image-id"], "sha256:" + ("b" * 64))
        self.assertEqual(properties["goreecloud:scanner"], "Trivy 0.74.0")

    def test_evaluation_error_report_is_sanitized_and_fails_closed(self):
        with TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            raw = temp / "raw.json"
            raw.write_text('{"secret detail":', encoding="utf-8")
            policy = temp / "policy.json"
            policy.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "policy": {
                            "blocking_severities": ["HIGH", "CRITICAL"],
                            "require_os_package_result": True,
                        },
                        "exceptions": [],
                    }
                ),
                encoding="utf-8",
            )
            dockerfile = temp / "Dockerfile"
            dockerfile.write_text(
                "FROM python:3.14.6-slim@sha256:" + ("a" * 64) + "\n",
                encoding="utf-8",
            )
            output = temp / "summary.json"
            exit_code = security.command_evaluate(
                SimpleNamespace(
                    input=str(raw),
                    policy=str(policy),
                    output=str(output),
                    dockerfile=str(dockerfile),
                    source_revision="a" * 40,
                    image_reference="manager:test",
                    image_id="sha256:" + ("b" * 64),
                    scanner_version="0.74.0",
                )
            )
            report = json.loads(output.read_text(encoding="utf-8"))

        self.assertEqual(exit_code, 2)
        self.assertEqual(report["status"], "error")
        self.assertEqual(report["error_type"], "JSONDecodeError")
        self.assertNotIn("secret detail", json.dumps(report))
