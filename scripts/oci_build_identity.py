#!/usr/bin/env python3
"""Generate and verify GoreeCloud Manager OCI build-identity evidence.

The evidence binds the exact loaded Docker image/config digest to the OCI image
manifest digest emitted by the same `docker buildx build --load` operation. It
does not publish an image, create a registry release, deploy Manager, or satisfy
target-environment production-readiness evidence.
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
SUPPORTED_MANIFEST_MEDIA_TYPES = {
    "application/vnd.oci.image.manifest.v1+json",
    "application/vnd.docker.distribution.manifest.v2+json",
}


def validate_sha256_digest(value: str, *, label: str) -> str:
    digest = value.strip().lower()
    if not SHA256_DIGEST.fullmatch(digest):
        raise ValueError(f"{label} must be a sha256:<64-hex> digest")
    return digest


def read_json_object(path: Path, *, label: str) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{label} must be a JSON object")
    return payload


def validate_build_metadata(
    payload: dict[str, Any], *, expected_image_id: str
) -> dict[str, Any]:
    image_id = provenance.validate_image_id(expected_image_id)
    config_digest = validate_sha256_digest(
        str(payload.get("containerimage.config.digest", "")),
        label="Buildx config digest",
    )
    if config_digest != image_id:
        raise ValueError("Buildx config digest does not match the loaded Docker image ID")

    manifest_digest = validate_sha256_digest(
        str(payload.get("containerimage.digest", "")),
        label="Buildx manifest digest",
    )
    descriptor = payload.get("containerimage.descriptor")
    if not isinstance(descriptor, dict):
        raise ValueError("Buildx metadata is missing the image descriptor")

    descriptor_digest = validate_sha256_digest(
        str(descriptor.get("digest", "")),
        label="Buildx descriptor digest",
    )
    if descriptor_digest != manifest_digest:
        raise ValueError("Buildx descriptor digest does not match the manifest digest")

    media_type = str(descriptor.get("mediaType", ""))
    if media_type not in SUPPORTED_MANIFEST_MEDIA_TYPES:
        raise ValueError("Buildx descriptor media type is not an accepted image manifest type")

    size = descriptor.get("size")
    if not isinstance(size, int) or isinstance(size, bool) or size <= 0:
        raise ValueError("Buildx descriptor size must be a positive integer")

    annotations = descriptor.get("annotations")
    if annotations is not None:
        if not isinstance(annotations, dict):
            raise ValueError("Buildx descriptor annotations are malformed")
        annotated_config = annotations.get("config.digest")
        if annotated_config is not None:
            annotated_digest = validate_sha256_digest(
                str(annotated_config),
                label="Buildx annotated config digest",
            )
            if annotated_digest != config_digest:
                raise ValueError(
                    "Buildx annotated config digest does not match the config digest"
                )

    return {
        "config_digest": config_digest,
        "manifest_digest": manifest_digest,
        "descriptor": {
            "digest": descriptor_digest,
            "media_type": media_type,
            "size_bytes": size,
        },
    }


def build_identity(
    *,
    inspection: dict[str, Any],
    build_metadata: dict[str, Any],
    source_revision: str,
    image_reference: str,
) -> dict[str, Any]:
    revision = provenance.validate_source_revision(source_revision)
    image = provenance.validate_image_contract(
        inspection,
        source_revision=revision,
        image_reference=image_reference,
    )
    build_output = validate_build_metadata(
        build_metadata,
        expected_image_id=image["id"],
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
            "loaded_image_matches_buildx_config_digest": True,
            "oci_manifest_digest_recorded": True,
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
    source_revision: str,
    image_reference: str,
) -> None:
    expected = build_identity(
        inspection=inspection,
        build_metadata=build_metadata,
        source_revision=source_revision,
        image_reference=image_reference,
    )
    if payload != expected:
        raise ValueError("OCI build-identity evidence no longer matches the exact build")


def command_generate(args: argparse.Namespace) -> int:
    payload = build_identity(
        inspection=provenance.inspect_image(args.image_reference),
        build_metadata=read_json_object(
            Path(args.build_metadata),
            label="Buildx metadata",
        ),
        source_revision=args.source_revision,
        image_reference=args.image_reference,
    )
    provenance.write_json(Path(args.output), payload)
    return 0


def command_verify(args: argparse.Namespace) -> int:
    payload = read_json_object(
        Path(args.input),
        label="OCI build-identity input",
    )
    verify_record(
        payload,
        inspection=provenance.inspect_image(args.image_reference),
        build_metadata=read_json_object(
            Path(args.build_metadata),
            label="Buildx metadata",
        ),
        source_revision=args.source_revision,
        image_reference=args.image_reference,
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    generate = subparsers.add_parser("generate", help="generate OCI build identity JSON")
    generate.add_argument("--image-reference", required=True)
    generate.add_argument("--source-revision", required=True)
    generate.add_argument("--build-metadata", required=True)
    generate.add_argument("--output", required=True)
    generate.set_defaults(handler=command_generate)

    verify = subparsers.add_parser("verify", help="verify OCI build identity JSON")
    verify.add_argument("--image-reference", required=True)
    verify.add_argument("--source-revision", required=True)
    verify.add_argument("--build-metadata", required=True)
    verify.add_argument("--input", required=True)
    verify.set_defaults(handler=command_verify)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        return int(args.handler(args))
    except (OSError, subprocess.CalledProcessError, json.JSONDecodeError, ValueError) as exc:
        print(f"OCI build identity error: {type(exc).__name__}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
