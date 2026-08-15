"""Release-provenance evidence contract tests."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPOSITORY_ROOT / "scripts" / "release_provenance.py"
spec = importlib.util.spec_from_file_location("manager_release_provenance", SCRIPT_PATH)
if spec is None or spec.loader is None:  # pragma: no cover
    raise RuntimeError("Unable to load release-provenance script")
provenance = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = provenance
spec.loader.exec_module(provenance)


def synthetic_inspection(revision: str, image_reference: str) -> dict:
    labels = dict(provenance.OCI_LABELS)
    labels["org.opencontainers.image.revision"] = revision
    return {
        "Id": "sha256:" + ("b" * 64),
        "RepoTags": [image_reference],
        "RepoDigests": [],
        "Config": {"Labels": labels},
    }


class ReleaseProvenanceTests(TestCase):
    def test_source_revision_requires_full_git_sha(self):
        revision = "a" * 40
        self.assertEqual(provenance.validate_source_revision(revision), revision)
        with self.assertRaisesRegex(ValueError, "40-character"):
            provenance.validate_source_revision("deadbeef")

    def test_image_contract_requires_exact_oci_revision_and_identity(self):
        revision = "a" * 40
        image_reference = f"goreecloud-manager-security:{revision}"
        inspection = synthetic_inspection(revision, image_reference)
        image = provenance.validate_image_contract(
            inspection,
            source_revision=revision,
            image_reference=image_reference,
        )
        self.assertEqual(image["id"], "sha256:" + ("b" * 64))
        self.assertEqual(
            image["oci_labels"]["org.opencontainers.image.revision"], revision
        )

        inspection["Config"]["Labels"]["org.opencontainers.image.revision"] = "c" * 40
        with self.assertRaisesRegex(ValueError, "OCI label"):
            provenance.validate_image_contract(
                inspection,
                source_revision=revision,
                image_reference=image_reference,
            )

    def test_provenance_binds_material_and_security_evidence_hashes(self):
        revision = "a" * 40
        image_reference = f"goreecloud-manager-security:{revision}"
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            material = root / "Dockerfile"
            evidence = root / "security-artifacts" / "report.json"
            evidence.parent.mkdir(parents=True)
            material.write_text("FROM scratch\n", encoding="utf-8")
            evidence.write_text('{"status":"pass"}\n', encoding="utf-8")

            payload = provenance.build_provenance(
                inspection=synthetic_inspection(revision, image_reference),
                source_revision=revision,
                image_reference=image_reference,
                materials=[material],
                evidence=[evidence],
                repository_root=root,
            )
            provenance.verify_record(
                payload,
                inspection=synthetic_inspection(revision, image_reference),
                source_revision=revision,
                image_reference=image_reference,
                repository_root=root,
            )
            evidence.write_text('{"status":"changed"}\n', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "digest mismatch"):
                provenance.verify_record(
                    payload,
                    inspection=synthetic_inspection(revision, image_reference),
                    source_revision=revision,
                    image_reference=image_reference,
                    repository_root=root,
                )

    def test_provenance_never_claims_deployment_or_production_approval(self):
        revision = "a" * 40
        image_reference = f"goreecloud-manager-security:{revision}"
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            material = root / "Dockerfile"
            evidence = root / "evidence.json"
            material.write_text("FROM scratch\n", encoding="utf-8")
            evidence.write_text("{}\n", encoding="utf-8")
            payload = provenance.build_provenance(
                inspection=synthetic_inspection(revision, image_reference),
                source_revision=revision,
                image_reference=image_reference,
                materials=[material],
                evidence=[evidence],
                repository_root=root,
            )

        self.assertTrue(payload["claims"]["exact_ci_image_identity_recorded"])
        self.assertFalse(payload["claims"]["registry_distribution_digest_recorded"])
        self.assertFalse(payload["claims"]["deployment_performed"])
        self.assertFalse(payload["claims"]["target_environment_production_readiness_satisfied"])
        self.assertFalse(payload["claims"]["production_approved"])

    def test_repository_contract_embeds_and_verifies_exact_revision(self):
        dockerfile = (REPOSITORY_ROOT / "Dockerfile").read_text(encoding="utf-8")
        workflow = (REPOSITORY_ROOT / ".github/workflows/ci.yml").read_text(
            encoding="utf-8"
        )

        self.assertIn("ARG MANAGER_SOURCE_REVISION=local", dockerfile)
        self.assertIn("org.opencontainers.image.revision=\"${MANAGER_SOURCE_REVISION}\"", dockerfile)
        self.assertIn("org.opencontainers.image.source=\"https://github.com/GoreeCloud/goreecloud-manager\"", dockerfile)
        self.assertIn("--build-arg MANAGER_SOURCE_REVISION=\"$MANAGER_SOURCE_REVISION\"", workflow)
        self.assertIn("scripts/release_provenance.py generate", workflow)
        self.assertIn("scripts/release_provenance.py verify", workflow)
        self.assertIn("goreecloud-manager-release-provenance.json", workflow)
        self.assertIn("steps.release_provenance.outcome", workflow)
        self.assertIn("path: security-artifacts/", workflow)
        self.assertRegex(
            workflow,
            r"actions/upload-artifact@[0-9a-f]{40}",
        )

    def test_generated_json_is_stable_and_machine_readable(self):
        revision = "a" * 40
        image_reference = f"goreecloud-manager-security:{revision}"
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            material = root / "requirements.lock"
            evidence = root / "report.json"
            output = root / "provenance.json"
            material.write_text("Django==5.2.17\n", encoding="utf-8")
            evidence.write_text("{}\n", encoding="utf-8")
            payload = provenance.build_provenance(
                inspection=synthetic_inspection(revision, image_reference),
                source_revision=revision,
                image_reference=image_reference,
                materials=[material],
                evidence=[evidence],
                repository_root=root,
            )
            provenance.write_json(output, payload)
            decoded = json.loads(output.read_text(encoding="utf-8"))

        self.assertEqual(decoded["schema_version"], 1)
        self.assertEqual(decoded["source"]["revision"], revision)
        self.assertEqual(decoded["image"]["id"], "sha256:" + ("b" * 64))
