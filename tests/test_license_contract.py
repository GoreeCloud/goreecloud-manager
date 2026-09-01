"""Repository and binary-distribution licensing contract tests."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from unittest import TestCase

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


class LicenseContractTests(TestCase):
    def test_repository_license_is_agpl_3_only(self):
        license_text = (REPOSITORY_ROOT / "LICENSE").read_text(encoding="utf-8")
        notice = (REPOSITORY_ROOT / "LICENSE-NOTICE.md").read_text(encoding="utf-8")
        self.assertIn("SPDX-License-Identifier: AGPL-3.0-only", license_text)
        self.assertIn("version 3 only", license_text)
        self.assertIn("SPDX identifier: `AGPL-3.0-only`", notice)
        self.assertIn("does not automatically opt into a future license version", notice)
        self.assertIn("Copyright (C) 2026 LaDamian Goree / GoreeCloud", notice)
        self.assertIn("previously distributed by GoreeCloud under the MIT License", license_text)

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

    def test_debian_builder_stages_source_and_license_material(self):
        builder = (REPOSITORY_ROOT / "packaging" / "build-deb.sh").read_text(encoding="utf-8")
        self.assertIn("/usr/share/doc/goreecloud-manager", builder)
        self.assertIn('install -m 0644 "${ROOT}/LICENSE"', builder)
        self.assertIn('install -m 0644 "${ROOT}/LICENSE-NOTICE.md"', builder)
        self.assertIn("fetch-agpl-license.py", builder)
        self.assertIn("AGPL-3.0.txt", builder)
        self.assertIn("THIRD_PARTY_NOTICES.md", builder)
        self.assertIn("collect-python-license-material.py", builder)
        self.assertIn("MANAGER_SOURCE_REVISION", builder)
        self.assertIn("Corresponding Source", builder)

    def test_canonical_agpl_fetch_is_immutable_and_fail_closed(self):
        fetcher = (REPOSITORY_ROOT / "packaging" / "fetch-agpl-license.py").read_text(encoding="utf-8")
        compile(fetcher, "fetch-agpl-license.py", "exec")
        self.assertIn("9d4f2bca2f754ab1eca7b518dd062b330689b969/LICENSE", fetcher)
        self.assertIn("be3f7b28e564e7dd05eaf59d64adba1a4065ac0e", fetcher)
        self.assertIn("git_blob_sha1", fetcher)
        self.assertIn("bounded download size", fetcher)
        self.assertIn("canonical AGPL text did not match the pinned Git blob identity", fetcher)

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
        self.assertIn("git archive --format=tar.gz", workflow)
        self.assertIn("goreecloud-manager-source-${MANAGER_SOURCE_REVISION}.tar.gz", workflow)
        self.assertGreaterEqual(workflow.count("dist/goreecloud-manager-source-*.tar.gz"), 3)
        self.assertIn("Prepare Android licensing assets", workflow)
        self.assertIn("android-client/app/src/main/assets/legal", workflow)
        self.assertIn("Verify Android licensing material", workflow)
        self.assertIn("assets/legal/LICENSE-NOTICE.md", workflow)
        self.assertIn("assets/legal/AGPL-3.0.txt", workflow)
        self.assertIn("assets/legal/SOURCE", workflow)
        self.assertIn("An exact corresponding-source archive accompanies this APK", workflow)
        self.assertIn("Verify packaged licensing material", workflow)
        self.assertIn("SPDX-License-Identifier: AGPL-3.0-only", workflow)
        self.assertIn("AGPL-3.0.txt", workflow)
        self.assertIn("GNU AFFERO GENERAL PUBLIC LICENSE", workflow)
        self.assertIn("third-party/MANIFEST.txt", workflow)
        self.assertIn("MANAGER_SOURCE_REVISION", workflow)
        self.assertIn("github.event.pull_request.head.sha || github.sha", workflow)

    def test_separate_notice_inventory_preserves_wardveil_boundary(self):
        notices = (REPOSITORY_ROOT / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8")
        self.assertIn("Wardveil Security", notices)
        self.assertIn("upstream MIT grant", notices)
        self.assertIn("PySide6", notices)
        self.assertIn("PyInstaller", notices)
        self.assertIn("CPython", notices)
