#!/usr/bin/env python3
"""Generate and verify GoreeCloud Manager OCI build-identity evidence.

The evidence binds the exact image ID emitted by Buildx to the exact image loaded
into Docker and to a real OCI/Docker image-distribution descriptor emitted by the
same non-publishing `type=image` build. It does not publish an image, create a
registry release, deploy Manager, or satisfy target-environment production-
readiness evidence.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path
from typing import Any

import release_provenance as provenance

SHA256_DIGEST = re.compile(r"^sha256:[0-9a-fA-F]{64}$")
SUPPORTED_DESCRIPTOR_MEDIA_TYPES = {
    "application/vnd.oci.image.manifest.v1+json": "image-manifest",
    "application/vnd.oci.image.index.v1+json": "image-index",
    "application/vnd.docker.distribution.manifest.v2+json": "image-manifest",
    "application/vnd.docker.distribution.manifest.list.v2+json": "image-index",
}


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


def read_json_object(path: Path, *, code: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise IdentityContractError(code) from exc
    if not isinstance(payload, dict):
        raise IdentityContractError(code)
    return payload


def read_buildx_image_id(path: Path) -> str:
    try:
        value = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise IdentityContractError("buildx-image-id-unreadable") from exc
    return require_sha256_digest(value, code="buildx-image-id-invalid")


def validate_build_metadata(
    payload: dict[str, Any], *, expected_image_id: str, buildx_image_id: str
) -> dict[str, Any]:
    try:
        loaded_image_id = provenance.validate_image_id(expected_image_id)
    except ValueError as exc:
        raise IdentityContractError("loaded-image-id-invalid") from exc

    emitted_image_id = require_sha256_digest(
        buildx_image_id,
        code="buildx-image-id-invalid",
    )
    if emitted_image_id != loaded_image_id:
        raise IdentityContractError("buildx-loaded-image-id-mismatch")

    raw_config_digest = payload.get("containerimage.config.digest")
    config_digest: str | None = None
    if raw_config_digest is not None:
        config_digest = require_sha256_digest(
            str(raw_config_digest),
            code="buildx-config-digest-invalid",
        )
        if config_digest != emitted_image_id:
            raise IdentityContractError("buildx-config-image-id-mismatch")

    distribution_digest = require_sha256_digest(
        str(payload.get("containerimage.digest", "")),
        code="buildx-distribution-digest-invalid",
    )

    descriptor = payload.get("containerimage.descriptor")
    if not isinstance(descriptor, dict):
        raise IdentityContractError("buildx-distribution-descriptor-missing")

    descriptor_digest = require_sha256_digest(
        str(descriptor.get("digest", "")),
        code="buildx-descriptor-digest-invalid",
    )
    if descriptor_digest != distribution_digest:
        raise IdentityContractError("buildx-descriptor-digest-mismatch")

    media_type = str(descriptor.get("mediaType", ""))
    descriptor_kind = SUPPORTED_DESCRIPTOR_MEDIA_TYPES.get(media_type)
    if descriptor_kind is None:
        raise IdentityContractError("buildx-descriptor-media-type-unsupported")

    size = descriptor.get("size")
    if not isinstance(size, int) or isinstance(size, bool) or size <= 0:
        raise IdentityContractError("buildx-descriptor-size-invalid")

    return {
        "buildx_image_id": emitted_image_id,
        "config_digest": config_digest,
        "distribution_digest": distribution_digest,
        "descriptor": {
            "digest": descriptor_digest,
            "kind": descriptor_kind,
            "media_type": media_type,
            "size_bytes": size,
        },
    }


def build_identity(
    *,
    inspection: dict[str, Any],
    build_metadata: dict[str, Any],
    buildx_image_id: str,
    source_revision: str,
    image_reference: str,
) -> dict[str, Any]:
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

    build_output = validate_build_metadata(
        build_metadata,
        expected_image_id=image["id"],
        buildx_image_id=buildx_image_id,
    )
    return {
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
            "build_output": build_output,
        },
        "claims": {
            "buildx_image_id_matches_loaded_image": True,
            "buildx_distribution_descriptor_recorded": True,
            "registry_distribution_digest_observed": bool(image["repo_digests"]),
            "registry_publication_performed": False,
            "deployment_performed": False,
            "target_environment_production_readiness_satisfied": False,
            "production_approved": False,
        },
    }


def verify_record(
    payload: dict[str, Any],
    *,
    inspection: dict[str, Any],
    build_metadata: dict[str, Any],
    buildx_image_id: str,
    source_revision: str,
    image_reference: str,
) -> None:
    expected = build_identity(
        inspection=inspection,
        build_metadata=build_metadata,
        buildx_image_id=buildx_image_id,
        source_revision=source_revision,
        image_reference=image_reference,
    )
    if payload != expected:
        raise IdentityContractError("identity-record-mismatch")


def command_generate(args: argparse.Namespace) -> int:
    payload = build_identity(
        inspection=provenance.inspect_image(args.image_reference),
        build_metadata=read_json_object(
            Path(args.build_metadata),
            code="buildx-metadata-invalid",
        ),
        buildx_image_id=read_buildx_image_id(Path(args.buildx_image_id_file)),
        source_revision=args.source_revision,
        image_reference=args.image_reference,
    )
    provenance.write_json(Path(args.output), payload)
    return 0


def command_verify(args: argparse.Namespace) -> int:
    payload = read_json_object(
        Path(args.input),
        code="identity-record-invalid",
    )
    verify_record(
        payload,
        inspection=provenance.inspect_image(args.image_reference),
        build_metadata=read_json_object(
            Path(args.build_metadata),
            code="buildx-metadata-invalid",
        ),
        buildx_image_id=read_buildx_image_id(Path(args.buildx_image_id_file)),
        source_revision=args.source_revision,
        image_reference=args.image_reference,
    )
    return 0


def add_common_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--image-reference", required=True)
    parser.add_argument("--source-revision", required=True)
    parser.add_argument("--build-metadata", required=True)
    parser.add_argument("--buildx-image-id-file", required=True)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    generate = subparsers.add_parser("generate", help="generate OCI build identity JSON")
    add_common_arguments(generate)
    generate.add_argument("--output", required=True)
    generate.set_defaults(handler=command_generate)

    verify = subparsers.add_parser("verify", help="verify OCI build identity JSON")
    add_common_arguments(verify)
    verify.add_argument("--input", required=True)
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
