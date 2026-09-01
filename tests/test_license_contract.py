"""Repository and binary-distribution licensing contract tests."""

from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path
from unittest import TestCase

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
APPROVED_AGPL_BLOB = "be3f7b28e564e7dd05eaf59d64adba1a4065ac0e"


def git_blob_sha1(payload: bytes) -> str:
    header = f"blob {len(payload)}\0".encode("ascii")
    return hashlib.sha1(header + payload, usedforsecurity=False).hexdigest()


class LicenseContractTests(TestCase):
    def test_repository_license_is_byte_exact_agplv3_and_notice_selects_v3_only(self):
        license_bytes = (REPOSITORY_ROOT / "LICENSE").read_bytes()
        license_text = license_bytes.decode("utf-8")
        notice = (REPOSITORY_ROOT / "LICENSE-NOTICE.md").read_text(encoding="utf-8")

        self.assertEqual(git_blob_sha1(license_bytes), APPROVED_AGPL_BLOB)
        self.assertIn("GNU AFFERO GENERAL PUBLIC LICENSE", license_text)
        self.assertIn("Version 3, 19 November 2007", license_text)
        self.assertIn("SPDX identifier: `AGPL-3.0-only`", notice)
        self.assertIn("does not automatically opt into a future license version", notice)
        self.assertIn("Copyright (C) 2026 LaDamian Goree / GoreeCloud", notice)
        self.assertIn("previously distributed under the MIT License", notice)

    def test_readme_records_prospective_relicense_and_prior_grants(self):
        readme = (REPOSITORY_ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("Current GoreeCloud Manager source is licensed under `AGPL-3.0-only`", readme)
        self.assertIn("previously distributed under the MIT License remain usable", readme)
        self.assertIn("THIRD_PARTY_NOTICES.md", readme)

    def test_container_and_release_provenance_agree_on_license(self):
        dockerfile = (REPOSITORY_ROOT / "Dockerfile").read_text(encoding="utf-8")
        provenance_path = REPOSITORY_ROOT / "scripts" / "release_provenance.py"
        self.assertIn('org.opencontainers.image.licenses="AGPL-3.0-only"', dockerfile)
        self.assertNotIn('org.opencontainers.image.licenses="MIT"', dockerfile)

        spec = importlib.util.spec_from_file_location("manager_release_provenance_license", provenance_path)
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader if spec else None)
        module = importlib.util.module_from_spec(spec)
        assert spec is not None and spec.loader is not None
        spec.loader.exec_module(module)
        self.assertEqual(module.OCI_LABELS["org.opencontainers.image.licenses"], "AGPL-3.0-only")

    def test_debian_builder_stages_and_verifies_repository_license_material(self):
        builder = (REPOSITORY_ROOT / "packaging" / "build-deb.sh").read_text(encoding="utf-8")
        self.assertIn("/usr/share/doc/goreecloud-manager", builder)
        self.assertIn('install -m 0644 "${ROOT}/LICENSE"', builder)
        self.assertIn('install -m 0644 "${ROOT}/LICENSE-NOTICE.md"', builder)
        self.assertIn(APPROVED_AGPL_BLOB, builder)
        self.assertIn("THIRD_PARTY_NOTICES.md", builder)
        self.assertIn("collect-python-license-material.py", builder)
        self.assertIn("MANAGER_SOURCE_REVISION", builder)
        self.assertIn("Corresponding Source", builder)
        self.assertNotIn("fetch-agpl-license.py", builder)
        self.assertNotIn("AGPL-3.0.txt", builder)

    def test_license_collector_is_fail_closed_for_expected_runtime(self):
        collector = (REPOSITORY_ROOT / "packaging" / "collect-python-license-material.py").read_text(
            encoding="utf-8"
        )
        compile(collector, "collect-python-license-material.py", "exec")
        for distribution in (
            "PySide6",
            "PySide6_Addons",
            "PySide6_Essentials",
            "shiboken6",
            "psutil",
            "PyYAML",
            "pyinstaller",
        ):
            self.assertIn(f'"{distribution}"', collector)
        self.assertIn("relative.is_absolute()", collector)
        self.assertIn('".." in relative.parts', collector)
        self.assertIn('doc_root / f"python{major}.{minor}" / "copyright"', collector)
        self.assertIn("required bundled distribution exposes no installed license material", collector)
        self.assertIn("packaged Python runtime license/copyright material was not found", collector)

    def test_client_packaging_revalidates_license_changes_and_package_contents(self):
        workflow = (REPOSITORY_ROOT / ".github" / "workflows" / "client-packaging.yml").read_text(
            encoding="utf-8"
        )
        self.assertGreaterEqual(workflow.count("- 'LICENSE'"), 2)
        self.assertGreaterEqual(workflow.count("- 'LICENSE-NOTICE.md'"), 2)
        self.assertGreaterEqual(workflow.count("- 'THIRD_PARTY_NOTICES.md'"), 2)
        self.assertEqual(workflow.count("Create exact corresponding-source archive"), 2)
        self.assertEqual(workflow.count('git config --global --add safe.directory "${GITHUB_WORKSPACE}"'), 1)
        self.assertIn(f"MANAGER_AGPL_BLOB: {APPROVED_AGPL_BLOB}", workflow)
        self.assertIn("git archive --format=tar.gz", workflow)
        self.assertIn("goreecloud-manager-source-${MANAGER_SOURCE_REVISION}.tar.gz", workflow)
        self.assertGreaterEqual(workflow.count("dist/goreecloud-manager-source-*.tar.gz"), 3)
        self.assertIn("Prepare Android licensing assets", workflow)
        self.assertIn("android-client/app/src/main/assets/legal", workflow)
        self.assertIn("Verify Android licensing material", workflow)
        self.assertIn("assets/legal/LICENSE-NOTICE.md", workflow)
        self.assertIn("assets/legal/LICENSE", workflow)
        self.assertIn("assets/legal/SOURCE", workflow)
        self.assertIn("An exact corresponding-source archive accompanies this APK", workflow)
        self.assertIn("Verify packaged licensing material", workflow)
        self.assertIn("git hash-object --stdin", workflow)
        self.assertIn("GNU AFFERO GENERAL PUBLIC LICENSE", workflow)
        self.assertIn("third-party/MANIFEST.txt", workflow)
        self.assertIn("MANAGER_SOURCE_REVISION", workflow)
        self.assertIn("github.event.pull_request.head.sha || github.sha", workflow)
        self.assertNotIn("fetch-agpl-license.py", workflow)
        self.assertNotIn("AGPL-3.0.txt", workflow)

    def test_separate_notice_inventory_preserves_wardveil_boundary(self):
        notices = (REPOSITORY_ROOT / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8")
        self.assertIn("Wardveil Security", notices)
        self.assertIn("upstream MIT grant", notices)
        self.assertIn("PySide6", notices)
        self.assertIn("PyInstaller", notices)
        self.assertIn("CPython", notices)
