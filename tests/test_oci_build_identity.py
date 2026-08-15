"""OCI build-identity evidence contract tests."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_ROOT = REPOSITORY_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

SCRIPT_PATH = SCRIPTS_ROOT / "oci_build_identity.py"
spec = importlib.util.spec_from_file_location("manager_oci_build_identity", SCRIPT_PATH)
if spec is None or spec.loader is None:  # pragma: no cover
    raise RuntimeError("Unable to load OCI build-identity script")
identity = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = identity
spec.loader.exec_module(identity)


def synthetic_inspection(revision: str, image_reference: str) -> dict:
    labels = dict(identity.provenance.OCI_LABELS)
    labels["org.opencontainers.image.revision"] = revision
    return {
        "Id": "sha256:" + ("b" * 64),
        "RepoTags": [image_reference],
        "RepoDigests": [],
        "Config": {"Labels": labels},
    }


def synthetic_build_metadata(
    *,
    image_id: str = "sha256:" + ("b" * 64),
    distribution_digest: str = "sha256:" + ("c" * 64),
    media_type: str = "application/vnd.oci.image.manifest.v1+json",
) -> dict:
    return {
        "containerimage.config.digest": image_id,
        "containerimage.digest": distribution_digest,
        "containerimage.descriptor": {
            "annotations": {"config.digest": image_id},
            "digest": distribution_digest,
            "mediaType": media_type,
            "size": 1234,
        },
    }


class OciBuildIdentityTests(TestCase):
    def test_build_metadata_requires_loaded_image_config_digest_match(self):
        parsed = identity.validate_build_metadata(
            synthetic_build_metadata(),
            expected_image_id="sha256:" + ("b" * 64),
        )
        self.assertEqual(parsed["config_digest"], "sha256:" + ("b" * 64))
        self.assertEqual(parsed["distribution_digest"], "sha256:" + ("c" * 64))

        with self.assertRaisesRegex(ValueError, "loaded Docker image ID"):
            identity.validate_build_metadata(
                synthetic_build_metadata(image_id="sha256:" + ("d" * 64)),
                expected_image_id="sha256:" + ("b" * 64),
            )

    def test_build_metadata_requires_descriptor_digest_match(self):
        metadata = synthetic_build_metadata()
        metadata["containerimage.descriptor"]["digest"] = "sha256:" + ("d" * 64)
        with self.assertRaisesRegex(ValueError, "descriptor digest"):
            identity.validate_build_metadata(
                metadata,
                expected_image_id="sha256:" + ("b" * 64),
            )

    def test_build_metadata_accepts_manifest_and_index_descriptors(self):
        for media_type, expected_kind in (
            ("application/vnd.oci.image.manifest.v1+json", "image-manifest"),
            ("application/vnd.docker.distribution.manifest.v2+json", "image-manifest"),
            ("application/vnd.oci.image.index.v1+json", "image-index"),
            ("application/vnd.docker.distribution.manifest.list.v2+json", "image-index"),
        ):
            with self.subTest(media_type=media_type):
                parsed = identity.validate_build_metadata(
                    synthetic_build_metadata(media_type=media_type),
                    expected_image_id="sha256:" + ("b" * 64),
                )
                self.assertEqual(parsed["descriptor"]["kind"], expected_kind)

    def test_build_metadata_rejects_non_image_distribution_descriptor(self):
        metadata = synthetic_build_metadata(
            media_type="application/vnd.oci.image.layer.v1.tar+gzip"
        )
        with self.assertRaisesRegex(ValueError, "image manifest or image index"):
            identity.validate_build_metadata(
                metadata,
                expected_image_id="sha256:" + ("b" * 64),
            )

    def test_identity_binds_source_image_and_distribution_digest_without_publication(self):
        revision = "a" * 40
        image_reference = f"goreecloud-manager-security:{revision}"
        payload = identity.build_identity(
            inspection=synthetic_inspection(revision, image_reference),
            build_metadata=synthetic_build_metadata(),
            source_revision=revision,
            image_reference=image_reference,
        )

        self.assertEqual(payload["schema_version"], 1)
        self.assertEqual(payload["source"]["revision"], revision)
        self.assertEqual(payload["image"]["id"], "sha256:" + ("b" * 64))
        self.assertEqual(
            payload["image"]["build_output"]["distribution_digest"],
            "sha256:" + ("c" * 64),
        )
        self.assertTrue(payload["claims"]["loaded_image_matches_buildx_config_digest"])
        self.assertTrue(payload["claims"]["buildx_distribution_digest_recorded"])
        self.assertFalse(payload["claims"]["registry_publication_performed"])
        self.assertFalse(payload["claims"]["deployment_performed"])
        self.assertFalse(payload["claims"]["production_approved"])

    def test_verify_fails_when_distribution_digest_changes(self):
        revision = "a" * 40
        image_reference = f"goreecloud-manager-security:{revision}"
        payload = identity.build_identity(
            inspection=synthetic_inspection(revision, image_reference),
            build_metadata=synthetic_build_metadata(),
            source_revision=revision,
            image_reference=image_reference,
        )
        with self.assertRaisesRegex(ValueError, "exact build"):
            identity.verify_record(
                payload,
                inspection=synthetic_inspection(revision, image_reference),
                build_metadata=synthetic_build_metadata(
                    distribution_digest="sha256:" + ("d" * 64)
                ),
                source_revision=revision,
                image_reference=image_reference,
            )

    def test_repository_contract_uses_buildx_and_retains_sanitized_identity(self):
        workflow = (REPOSITORY_ROOT / ".github/workflows/ci.yml").read_text(
            encoding="utf-8"
        )

        self.assertIn("docker buildx build", workflow)
        self.assertIn("--load", workflow)
        self.assertIn('--metadata-file "$metadata_file"', workflow)
        self.assertIn("BUILDX_METADATA_PROVENANCE=disabled", workflow)
        self.assertIn("scripts/oci_build_identity.py generate", workflow)
        self.assertIn("scripts/oci_build_identity.py verify", workflow)
        self.assertIn("goreecloud-manager-oci-build-identity.json", workflow)
        self.assertIn(
            "--evidence security-artifacts/goreecloud-manager-oci-build-identity.json",
            workflow,
        )
        self.assertIn("steps.oci_build_identity.outcome", workflow)
        self.assertNotIn(
            "path: $RUNNER_TEMP/manager-build-metadata.json",
            workflow,
        )

    def test_json_output_is_stable_and_machine_readable(self):
        revision = "a" * 40
        image_reference = f"goreecloud-manager-security:{revision}"
        payload = identity.build_identity(
            inspection=synthetic_inspection(revision, image_reference),
            build_metadata=synthetic_build_metadata(),
            source_revision=revision,
            image_reference=image_reference,
        )
        with TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "identity.json"
            identity.provenance.write_json(output, payload)
            decoded = json.loads(output.read_text(encoding="utf-8"))

        self.assertEqual(decoded["evidence_type"], "exact-oci-build-identity")
        self.assertEqual(
            decoded["image"]["build_output"]["distribution_digest"],
            "sha256:" + ("c" * 64),
        )
