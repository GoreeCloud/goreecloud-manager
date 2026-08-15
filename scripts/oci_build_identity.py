#!/usr/bin/env python3
"""Generate and verify GoreeCloud Manager OCI build-identity evidence.

The exact Buildx build emits both a locally loaded Docker image and an OCI image
layout tarball. This validator hashes the real OCI manifest blob and requires its
config digest to equal the loaded Docker image ID. It does not publish an image,
create a registry release, deploy Manager, or satisfy target-environment
production-readiness evidence.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import tarfile
from pathlib import Path
from typing import Any

import release_provenance as provenance

SHA256_DIGEST = re.compile(r"^sha256:[0-9a-fA-F]{64}$")
OCI_MANIFEST_MEDIA_TYPE = "application/vnd.oci.image.manifest.v1+json"
OCI_INDEX_MEDIA_TYPE = "application/vnd.oci.image.index.v1+json"
OCI_LAYOUT_VERSION = "1.0.0"


class IdentityContractError(ValueError):
    """Fail-closed identity error carrying only a safe static reason code."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def require_sha256_digest(value: str, *, code: str) -> str:
    digest = value.strip().lower()
    if not SHA256_DIGEST.fullmatch(digest):
        raise IdentityContractError(code)
    return digest


def sha256_bytes(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def parse_json_bytes(payload: bytes, *, code: str) -> dict[str, Any]:
    try:
        decoded = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise IdentityContractError(code) from exc
    if not isinstance(decoded, dict):
        raise IdentityContractError(code)
    return decoded


def read_tar_member(archive: tarfile.TarFile, name: str, *, code: str) -> bytes:
    try:
        member = archive.getmember(name)
    except KeyError as exc:
        raise IdentityContractError(code) from exc
    if not member.isfile() or member.size <= 0:
        raise IdentityContractError(code)
    handle = archive.extractfile(member)
    if handle is None:
        raise IdentityContractError(code)
    return handle.read()


def validate_oci_archive(path: Path, *, expected_image_id: str) -> dict[str, Any]:
    try:
        loaded_image_id = provenance.validate_image_id(expected_image_id)
    except ValueError as exc:
        raise IdentityContractError("loaded-image-id-invalid") from exc

    try:
        archive = tarfile.open(path, mode="r:*")
    except (OSError, tarfile.TarError) as exc:
        raise IdentityContractError("oci-archive-unreadable") from exc

    with archive:
        layout = parse_json_bytes(
            read_tar_member(archive, "oci-layout", code="oci-layout-missing"),
            code="oci-layout-invalid",
        )
        if layout.get("imageLayoutVersion") != OCI_LAYOUT_VERSION:
            raise IdentityContractError("oci-layout-version-invalid")

        index_bytes = read_tar_member(archive, "index.json", code="oci-index-missing")
        index = parse_json_bytes(index_bytes, code="oci-index-invalid")
        if index.get("schemaVersion") != 2:
            raise IdentityContractError("oci-index-schema-invalid")
        if index.get("mediaType") not in (None, OCI_INDEX_MEDIA_TYPE):
            raise IdentityContractError("oci-index-media-type-invalid")

        manifests = index.get("manifests")
        if not isinstance(manifests, list) or len(manifests) != 1:
            raise IdentityContractError("oci-index-manifest-count-invalid")
        descriptor = manifests[0]
        if not isinstance(descriptor, dict):
            raise IdentityContractError("oci-manifest-descriptor-invalid")
        if descriptor.get("mediaType") != OCI_MANIFEST_MEDIA_TYPE:
            raise IdentityContractError("oci-manifest-media-type-invalid")

        manifest_digest = require_sha256_digest(
            str(descriptor.get("digest", "")),
            code="oci-manifest-digest-invalid",
        )
        manifest_size = descriptor.get("size")
        if not isinstance(manifest_size, int) or isinstance(manifest_size, bool) or manifest_size <= 0:
            raise IdentityContractError("oci-manifest-size-invalid")

        manifest_hex = manifest_digest.removeprefix("sha256:")
        manifest_bytes = read_tar_member(
            archive,
            f"blobs/sha256/{manifest_hex}",
            code="oci-manifest-blob-missing",
        )
        if len(manifest_bytes) != manifest_size:
            raise IdentityContractError("oci-manifest-size-mismatch")
        if sha256_bytes(manifest_bytes) != manifest_digest:
            raise IdentityContractError("oci-manifest-hash-mismatch")

        manifest = parse_json_bytes(manifest_bytes, code="oci-manifest-invalid")
        if manifest.get("schemaVersion") != 2:
            raise IdentityContractError("oci-manifest-schema-invalid")
        if manifest.get("mediaType") not in (None, OCI_MANIFEST_MEDIA_TYPE):
            raise IdentityContractError("oci-manifest-content-media-type-invalid")

        config = manifest.get("config")
        if not isinstance(config, dict):
            raise IdentityContractError("oci-config-descriptor-invalid")
        config_digest = require_sha256_digest(
            str(config.get("digest", "")),
            code="oci-config-digest-invalid",
        )
        if config_digest != loaded_image_id:
            raise IdentityContractError("oci-config-loaded-image-mismatch")
        config_size = config.get("size")
        if not isinstance(config_size, int) or isinstance(config_size, bool) or config_size <= 0:
            raise IdentityContractError("oci-config-size-invalid")

        layers = manifest.get("layers")
        if not isinstance(layers, list) or not layers:
            raise IdentityContractError("oci-layer-list-invalid")
        for layer in layers:
            if not isinstance(layer, dict):
                raise IdentityContractError("oci-layer-descriptor-invalid")
            require_sha256_digest(
                str(layer.get("digest", "")),
                code="oci-layer-digest-invalid",
            )
            layer_size = layer.get("size")
            if not isinstance(layer_size, int) or isinstance(layer_size, bool) or layer_size <= 0:
                raise IdentityContractError("oci-layer-size-invalid")
            if not str(layer.get("mediaType", "")).startswith("application/vnd.oci.image.layer."):
                raise IdentityContractError("oci-layer-media-type-invalid")

        return {
            "index_sha256": sha256_bytes(index_bytes),
            "manifest_digest": manifest_digest,
            "manifest_media_type": OCI_MANIFEST_MEDIA_TYPE,
            "manifest_size_bytes": manifest_size,
            "manifest_bytes": manifest_bytes,
            "config_digest": config_digest,
            "config_size_bytes": config_size,
            "layer_count": len(layers),
        }


def build_identity(
    *,
    inspection: dict[str, Any],
    oci_archive: Path,
    source_revision: str,
    image_reference: str,
) -> tuple[dict[str, Any], bytes]:
    try:
        revision = provenance.validate_source_revision(source_revision)
    except ValueError as exc:
        raise IdentityContractError("source-revision-invalid") from exc
    try:
        image = provenance.validate_image_contract(
            inspection,
            source_revision=revision,
            image_reference=image_reference,
        )
    except ValueError as exc:
        raise IdentityContractError("loaded-image-contract-invalid") from exc

    archive_identity = validate_oci_archive(oci_archive, expected_image_id=image["id"])
    manifest_bytes = archive_identity.pop("manifest_bytes")
    payload = {
        "schema_version": 1,
        "project": provenance.PROJECT_NAME,
        "evidence_type": "exact-oci-build-identity",
        "source": {
            "repository": provenance.SOURCE_REPOSITORY,
            "revision": revision,
        },
        "image": {
            "reference": image["reference"],
            "id": image["id"],
            "repo_digests": image["repo_digests"],
            "oci_labels": image["oci_labels"],
            "oci_layout": archive_identity,
        },
        "claims": {
            "oci_manifest_config_matches_loaded_image": True,
            "oci_manifest_blob_hash_verified": True,
            "registry_distribution_digest_observed": bool(image["repo_digests"]),
            "registry_publication_performed": False,
            "deployment_performed": False,
            "target_environment_production_readiness_satisfied": False,
            "production_approved": False,
        },
    }
    return payload, manifest_bytes


def verify_manifest_file(path: Path, *, expected_digest: str) -> None:
    try:
        payload = path.read_bytes()
    except OSError as exc:
        raise IdentityContractError("retained-oci-manifest-unreadable") from exc
    if sha256_bytes(payload) != expected_digest:
        raise IdentityContractError("retained-oci-manifest-hash-mismatch")


def command_generate(args: argparse.Namespace) -> int:
    payload, manifest_bytes = build_identity(
        inspection=provenance.inspect_image(args.image_reference),
        oci_archive=Path(args.oci_archive),
        source_revision=args.source_revision,
        image_reference=args.image_reference,
    )
    output = Path(args.output)
    manifest_output = Path(args.manifest_output)
    provenance.write_json(output, payload)
    manifest_output.parent.mkdir(parents=True, exist_ok=True)
    manifest_output.write_bytes(manifest_bytes)
    verify_manifest_file(
        manifest_output,
        expected_digest=payload["image"]["oci_layout"]["manifest_digest"],
    )
    return 0


def command_verify(args: argparse.Namespace) -> int:
    try:
        payload = json.loads(Path(args.input).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise IdentityContractError("identity-record-invalid") from exc
    if not isinstance(payload, dict):
        raise IdentityContractError("identity-record-invalid")

    expected, _manifest_bytes = build_identity(
        inspection=provenance.inspect_image(args.image_reference),
        oci_archive=Path(args.oci_archive),
        source_revision=args.source_revision,
        image_reference=args.image_reference,
    )
    if payload != expected:
        raise IdentityContractError("identity-record-mismatch")
    verify_manifest_file(
        Path(args.manifest_input),
        expected_digest=expected["image"]["oci_layout"]["manifest_digest"],
    )
    return 0


def add_common_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--image-reference", required=True)
    parser.add_argument("--source-revision", required=True)
    parser.add_argument("--oci-archive", required=True)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    generate = subparsers.add_parser("generate", help="generate OCI build identity JSON")
    add_common_arguments(generate)
    generate.add_argument("--output", required=True)
    generate.add_argument("--manifest-output", required=True)
    generate.set_defaults(handler=command_generate)

    verify = subparsers.add_parser("verify", help="verify OCI build identity JSON")
    add_common_arguments(verify)
    verify.add_argument("--input", required=True)
    verify.add_argument("--manifest-input", required=True)
    verify.set_defaults(handler=command_verify)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        return int(args.handler(args))
    except IdentityContractError as exc:
        print(f"OCI build identity error: {exc.code}")
        return 2
    except (OSError, subprocess.CalledProcessError, json.JSONDecodeError, ValueError) as exc:
        print(f"OCI build identity error: unexpected-{type(exc).__name__}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
