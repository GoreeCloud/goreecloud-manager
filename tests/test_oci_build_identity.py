"""OCI build-identity evidence contract tests."""

from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import sys
import tarfile
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

BUILDER_IMAGE = (
    "moby/buildkit:buildx-stable-1@sha256:"
    "2f5adac4ecd194d9f8c10b7b5d7bceb5186853db1b26e5abd3a657af0b7e26ec"
)
CONFIG_BYTES = b'{"architecture":"amd64","os":"linux"}'
LAYER_BYTES = b"synthetic-goreecloud-manager-layer"
IMAGE_ID = "sha256:" + hashlib.sha256(CONFIG_BYTES).hexdigest()
LAYER_DIGEST = "sha256:" + hashlib.sha256(LAYER_BYTES).hexdigest()


def json_bytes(payload: dict) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def add_tar_bytes(archive: tarfile.TarFile, name: str, payload: bytes) -> None:
    info = tarfile.TarInfo(name=name)
    info.size = len(payload)
    info.mode = 0o644
    archive.addfile(info, io.BytesIO(payload))


def synthetic_inspection(revision: str, image_reference: str) -> dict:
    labels = dict(identity.provenance.OCI_LABELS)
    labels["org.opencontainers.image.revision"] = revision
    return {
        "Id": IMAGE_ID,
        "RepoTags": [image_reference],
        "RepoDigests": [],
        "Config": {"Labels": labels},
    }


def write_oci_archive(
    path: Path,
    *,
    config_bytes: bytes = CONFIG_BYTES,
    manifest_config_digest: str | None = None,
    layer_bytes: bytes = LAYER_BYTES,
    layer_digest: str | None = None,
    layer_media_type: str = "application/vnd.oci.image.layer.v1.tar+gzip",
    manifest_media_type: str = identity.OCI_MANIFEST_MEDIA_TYPE,
    manifest_count: int = 1,
    corrupt_manifest_blob: bool = False,
    corrupt_config_blob: bool = False,
    corrupt_layer_blob: bool = False,
) -> tuple[str, bytes]:
    config_digest = manifest_config_digest or (
        "sha256:" + hashlib.sha256(config_bytes).hexdigest()
    )
    layer_digest_value = layer_digest or (
        "sha256:" + hashlib.sha256(layer_bytes).hexdigest()
    )
    manifest = {
        "schemaVersion": 2,
        "mediaType": identity.OCI_MANIFEST_MEDIA_TYPE,
        "config": {
            "mediaType": "application/vnd.oci.image.config.v1+json",
            "digest": config_digest,
            "size": len(config_bytes),
        },
        "layers": [
            {
                "mediaType": layer_media_type,
                "digest": layer_digest_value,
                "size": len(layer_bytes),
            }
        ],
    }
    manifest_bytes = json_bytes(manifest)
    manifest_digest = "sha256:" + hashlib.sha256(manifest_bytes).hexdigest()
    descriptor = {
        "mediaType": manifest_media_type,
        "digest": manifest_digest,
        "size": len(manifest_bytes),
    }
    index = {
        "schemaVersion": 2,
        "mediaType": identity.OCI_INDEX_MEDIA_TYPE,
        "manifests": [descriptor for _ in range(manifest_count)],
    }

    manifest_blob = bytearray(manifest_bytes)
    if corrupt_manifest_blob:
        manifest_blob[-1] = ord(" ")
    config_blob = bytearray(config_bytes)
    if corrupt_config_blob:
        config_blob[-1] ^= 1
    layer_blob = bytearray(layer_bytes)
    if corrupt_layer_blob:
        layer_blob[-1] ^= 1

    with tarfile.open(path, mode="w") as archive:
        add_tar_bytes(
            archive,
            "oci-layout",
            json_bytes({"imageLayoutVersion": identity.OCI_LAYOUT_VERSION}),
        )
        add_tar_bytes(archive, "index.json", json_bytes(index))
        add_tar_bytes(
            archive,
            f"blobs/sha256/{manifest_digest.removeprefix('sha256:')}",
            bytes(manifest_blob),
        )
        add_tar_bytes(
            archive,
            f"blobs/sha256/{config_digest.removeprefix('sha256:')}",
            bytes(config_blob),
        )
        add_tar_bytes(
            archive,
            f"blobs/sha256/{layer_digest_value.removeprefix('sha256:')}",
            bytes(layer_blob),
        )
    return manifest_digest, manifest_bytes


class OciBuildIdentityTests(TestCase):
    def test_valid_oci_layout_binds_manifest_config_to_loaded_image(self):
        with TemporaryDirectory() as temp_dir:
            archive_path = Path(temp_dir) / "manager.oci.tar"
            manifest_digest, _ = write_oci_archive(archive_path)
            parsed = identity.validate_oci_archive(
                archive_path,
                expected_image_id=IMAGE_ID,
            )

        self.assertEqual(parsed["manifest_digest"], manifest_digest)
        self.assertEqual(parsed["config_digest"], IMAGE_ID)
        self.assertEqual(parsed["layer_count"], 1)
        self.assertEqual(parsed["layer_bytes"], len(LAYER_BYTES))

    def test_manifest_blob_hash_mismatch_fails_closed(self):
        with TemporaryDirectory() as temp_dir:
            archive_path = Path(temp_dir) / "manager.oci.tar"
            write_oci_archive(archive_path, corrupt_manifest_blob=True)
            with self.assertRaisesRegex(
                identity.IdentityContractError,
                "oci-manifest-hash-mismatch",
            ):
                identity.validate_oci_archive(archive_path, expected_image_id=IMAGE_ID)

    def test_manifest_config_must_match_loaded_docker_image(self):
        other_config = b'{"architecture":"arm64","os":"linux"}'
        other_digest = "sha256:" + hashlib.sha256(other_config).hexdigest()
        with TemporaryDirectory() as temp_dir:
            archive_path = Path(temp_dir) / "manager.oci.tar"
            write_oci_archive(
                archive_path,
                config_bytes=other_config,
                manifest_config_digest=other_digest,
            )
            with self.assertRaisesRegex(
                identity.IdentityContractError,
                "oci-config-loaded-image-mismatch",
            ):
                identity.validate_oci_archive(archive_path, expected_image_id=IMAGE_ID)

    def test_config_blob_hash_mismatch_fails_closed(self):
        with TemporaryDirectory() as temp_dir:
            archive_path = Path(temp_dir) / "manager.oci.tar"
            write_oci_archive(archive_path, corrupt_config_blob=True)
            with self.assertRaisesRegex(
                identity.IdentityContractError,
                "oci-config-hash-mismatch",
            ):
                identity.validate_oci_archive(archive_path, expected_image_id=IMAGE_ID)

    def test_layer_blob_hash_mismatch_fails_closed(self):
        with TemporaryDirectory() as temp_dir:
            archive_path = Path(temp_dir) / "manager.oci.tar"
            write_oci_archive(archive_path, corrupt_layer_blob=True)
            with self.assertRaisesRegex(
                identity.IdentityContractError,
                "oci-layer-hash-mismatch",
            ):
                identity.validate_oci_archive(archive_path, expected_image_id=IMAGE_ID)

    def test_index_requires_exactly_one_manifest(self):
        for count in (0, 2):
            with self.subTest(count=count), TemporaryDirectory() as temp_dir:
                archive_path = Path(temp_dir) / "manager.oci.tar"
                write_oci_archive(archive_path, manifest_count=count)
                with self.assertRaisesRegex(
                    identity.IdentityContractError,
                    "oci-index-manifest-count-invalid",
                ):
                    identity.validate_oci_archive(
                        archive_path,
                        expected_image_id=IMAGE_ID,
                    )

    def test_manifest_media_type_must_be_oci_image_manifest(self):
        with TemporaryDirectory() as temp_dir:
            archive_path = Path(temp_dir) / "manager.oci.tar"
            write_oci_archive(
                archive_path,
                manifest_media_type=identity.OCI_INDEX_MEDIA_TYPE,
            )
            with self.assertRaisesRegex(
                identity.IdentityContractError,
                "oci-manifest-media-type-invalid",
            ):
                identity.validate_oci_archive(archive_path, expected_image_id=IMAGE_ID)

    def test_layer_descriptor_requires_digest_media_type_and_size(self):
        with TemporaryDirectory() as temp_dir:
            archive_path = Path(temp_dir) / "manager.oci.tar"
            write_oci_archive(
                archive_path,
                layer_media_type="application/octet-stream",
            )
            with self.assertRaisesRegex(
                identity.IdentityContractError,
                "oci-layer-media-type-invalid",
            ):
                identity.validate_oci_archive(archive_path, expected_image_id=IMAGE_ID)

    def test_builder_image_must_be_digest_pinned(self):
        self.assertEqual(identity.validate_builder_image(BUILDER_IMAGE), BUILDER_IMAGE)
        with self.assertRaisesRegex(
            identity.IdentityContractError,
            "builder-image-not-digest-pinned",
        ):
            identity.validate_builder_image("moby/buildkit:buildx-stable-1")

    def test_identity_retains_minimized_verified_oci_contract(self):
        revision = "a" * 40
        image_reference = f"goreecloud-manager-security:{revision}"
        with TemporaryDirectory() as temp_dir:
            archive_path = Path(temp_dir) / "manager.oci.tar"
            manifest_digest, _ = write_oci_archive(archive_path)
            payload, _manifest_bytes = identity.build_identity(
                inspection=synthetic_inspection(revision, image_reference),
                oci_archive=archive_path,
                builder_image=BUILDER_IMAGE,
                source_revision=revision,
                image_reference=image_reference,
            )

        self.assertEqual(payload["source"]["revision"], revision)
        self.assertEqual(payload["build"]["builder_image"], BUILDER_IMAGE)
        self.assertEqual(
            payload["build"]["outputs"],
            ["docker-loaded-image", "oci-image-layout"],
        )
        self.assertEqual(payload["image"]["id"], IMAGE_ID)
        self.assertEqual(
            payload["image"]["oci_layout"]["manifest_digest"],
            manifest_digest,
        )
        self.assertEqual(payload["image"]["oci_layout"]["config_digest"], IMAGE_ID)
        self.assertTrue(payload["claims"]["oci_manifest_config_matches_loaded_image"])
        self.assertTrue(payload["claims"]["oci_manifest_blob_hash_verified"])
        self.assertTrue(payload["claims"]["oci_config_blob_hash_verified"])
        self.assertTrue(payload["claims"]["oci_layer_blob_hashes_verified"])
        self.assertFalse(payload["claims"]["registry_publication_performed"])
        self.assertFalse(payload["claims"]["deployment_performed"])
        self.assertFalse(payload["claims"]["production_approved"])

    def test_retained_manifest_hash_is_exact_manifest_digest(self):
        revision = "a" * 40
        image_reference = f"goreecloud-manager-security:{revision}"
        with TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            archive_path = temp / "manager.oci.tar"
            identity_path = temp / "identity.json"
            manifest_path = temp / "manifest.json"
            manifest_digest, _ = write_oci_archive(archive_path)
            payload, manifest_bytes = identity.build_identity(
                inspection=synthetic_inspection(revision, image_reference),
                oci_archive=archive_path,
                builder_image=BUILDER_IMAGE,
                source_revision=revision,
                image_reference=image_reference,
            )
            identity.provenance.write_json(identity_path, payload)
            manifest_path.write_bytes(manifest_bytes)
            identity.verify_manifest_file(
                manifest_path,
                expected_digest=manifest_digest,
            )
            manifest_path.write_bytes(manifest_bytes + b"\n")
            with self.assertRaisesRegex(
                identity.IdentityContractError,
                "retained-oci-manifest-hash-mismatch",
            ):
                identity.verify_manifest_file(
                    manifest_path,
                    expected_digest=manifest_digest,
                )

    def test_repository_contract_uses_pinned_builder_and_two_same_build_outputs(self):
        workflow = (REPOSITORY_ROOT / ".github/workflows/ci.yml").read_text(
            encoding="utf-8"
        )

        self.assertIn(f'BUILDKIT_IMAGE: "{BUILDER_IMAGE}"', workflow)
        self.assertIn("--driver docker-container", workflow)
        self.assertIn('--driver-opt "image=$BUILDKIT_IMAGE"', workflow)
        self.assertIn("docker buildx inspect --bootstrap", workflow)
        self.assertIn("--provenance=false", workflow)
        self.assertIn('--output "type=oci,dest=$oci_archive,oci-mediatypes=true"', workflow)
        self.assertIn("--load", workflow)
        self.assertNotIn("push=true", workflow)
        self.assertIn("MANAGER_OCI_ARCHIVE", workflow)
        self.assertIn("goreecloud-manager-oci-build-identity.json", workflow)
        self.assertIn("goreecloud-manager-oci-manifest.json", workflow)
        self.assertIn(
            "--evidence security-artifacts/goreecloud-manager-oci-build-identity.json",
            workflow,
        )
        self.assertIn(
            "--evidence security-artifacts/goreecloud-manager-oci-manifest.json",
            workflow,
        )
        self.assertIn("rm -f \"$MANAGER_OCI_ARCHIVE\"", workflow)
        self.assertNotIn("security-artifacts/goreecloud-manager.oci.tar", workflow)
