#!/usr/bin/env python3
"""Generate and verify GoreeCloud Manager release-provenance evidence.

This script binds an exact Git source revision to the exact locally built container
image identity used by CI and to the source/security evidence files that accompany
that build. It does not publish an image, create a registry digest, deploy Manager,
or satisfy target-environment production-readiness evidence.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any

PROJECT_NAME = "GoreeCloud Manager"
SOURCE_REPOSITORY = "https://github.com/GoreeCloud/goreecloud-manager"
OCI_LABELS = {
    "org.opencontainers.image.title": PROJECT_NAME,
    "org.opencontainers.image.source": SOURCE_REPOSITORY,
    "org.opencontainers.image.licenses": "AGPL-3.0-only",
    "org.opencontainers.image.vendor": "GoreeCloud",
}
FULL_GIT_SHA = re.compile(r"^[0-9a-fA-F]{40}$")
IMAGE_ID = re.compile(r"^sha256:[0-9a-f]{64}$")


def validate_source_revision(value: str) -> str:
    revision = value.strip().lower()
    if not FULL_GIT_SHA.fullmatch(revision):
        raise ValueError("source revision must be a full 40-character Git SHA")
    return revision


def validate_image_id(value: str) -> str:
    image_id = value.strip().lower()
    if not IMAGE_ID.fullmatch(image_id):
        raise ValueError("image identity must be a sha256:<64-hex> Docker image ID")
    return image_id


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def inspect_image(image_reference: str) -> dict[str, Any]:
    completed = subprocess.run(
        ["docker", "image", "inspect", image_reference],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(completed.stdout)
    if not isinstance(payload, list) or len(payload) != 1 or not isinstance(payload[0], dict):
        raise ValueError("docker image inspect returned an unexpected payload")
    return payload[0]


def validate_image_contract(
    inspection: dict[str, Any], *, source_revision: str, image_reference: str
) -> dict[str, Any]:
    revision = validate_source_revision(source_revision)
    image_id = validate_image_id(str(inspection.get("Id", "")))
    config = inspection.get("Config")
    if not isinstance(config, dict):
        raise ValueError("image inspection is missing Config")
    labels = config.get("Labels")
    if not isinstance(labels, dict):
        raise ValueError("image inspection is missing OCI labels")

    expected_labels = dict(OCI_LABELS)
    expected_labels["org.opencontainers.image.revision"] = revision
    for name, expected in expected_labels.items():
        actual = str(labels.get(name, ""))
        if actual != expected:
            raise ValueError(f"image OCI label {name!r} does not match the expected value")

    repo_tags = inspection.get("RepoTags") or []
    if image_reference not in repo_tags:
        raise ValueError("inspected image does not carry the expected CI image reference")

    repo_digests = inspection.get("RepoDigests") or []
    if not isinstance(repo_digests, list):
        raise ValueError("image RepoDigests field is malformed")

    return {
        "id": image_id,
        "reference": image_reference,
        "repo_digests": sorted(str(item) for item in repo_digests),
        "oci_labels": {name: expected_labels[name] for name in sorted(expected_labels)},
    }


def describe_file(path: Path, repository_root: Path) -> dict[str, Any]:
    resolved = path.resolve()
    try:
        relative = resolved.relative_to(repository_root.resolve())
    except ValueError as exc:
        raise ValueError(f"evidence path must stay inside the repository: {path}") from exc
    if not resolved.is_file():
        raise ValueError(f"required evidence file does not exist: {relative.as_posix()}")
    return {
        "path": relative.as_posix(),
        "sha256": sha256_file(resolved),
        "size_bytes": resolved.stat().st_size,
    }


def build_ci_metadata() -> dict[str, str | None]:
    return {
        "provider": "github-actions",
        "repository": os.environ.get("GITHUB_REPOSITORY"),
        "workflow": os.environ.get("GITHUB_WORKFLOW"),
        "workflow_ref": os.environ.get("GITHUB_WORKFLOW_REF"),
        "event_name": os.environ.get("GITHUB_EVENT_NAME"),
        "run_id": os.environ.get("GITHUB_RUN_ID"),
        "run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT"),
    }


def build_provenance(
    *,
    inspection: dict[str, Any],
    source_revision: str,
    image_reference: str,
    materials: list[Path],
    evidence: list[Path],
    repository_root: Path,
) -> dict[str, Any]:
    revision = validate_source_revision(source_revision)
    image = validate_image_contract(
        inspection,
        source_revision=revision,
        image_reference=image_reference,
    )
    material_records = [describe_file(path, repository_root) for path in materials]
    evidence_records = [describe_file(path, repository_root) for path in evidence]
    if len({item["path"] for item in material_records}) != len(material_records):
        raise ValueError("material paths must be unique")
    if len({item["path"] for item in evidence_records}) != len(evidence_records):
        raise ValueError("evidence paths must be unique")

    return {
        "schema_version": 1,
        "project": PROJECT_NAME,
        "evidence_type": "source-and-ci-image-provenance",
        "source": {
            "repository": SOURCE_REPOSITORY,
            "revision": revision,
        },
        "image": image,
        "materials": sorted(material_records, key=lambda item: item["path"]),
        "security_evidence": sorted(evidence_records, key=lambda item: item["path"]),
        "ci": build_ci_metadata(),
        "claims": {
            "exact_ci_image_identity_recorded": True,
            "registry_distribution_digest_recorded": bool(image["repo_digests"]),
            "deployment_performed": False,
            "target_environment_production_readiness_satisfied": False,
            "production_approved": False,
        },
    }


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def command_generate(args: argparse.Namespace) -> int:
    root = Path(args.repository_root).resolve()
    payload = build_provenance(
        inspection=inspect_image(args.image_reference),
        source_revision=args.source_revision,
        image_reference=args.image_reference,
        materials=[Path(item) for item in args.material],
        evidence=[Path(item) for item in args.evidence],
        repository_root=root,
    )
    write_json(Path(args.output), payload)
    return 0


def verify_record(
    payload: dict[str, Any],
    *,
    inspection: dict[str, Any],
    source_revision: str,
    image_reference: str,
    repository_root: Path,
) -> None:
    revision = validate_source_revision(source_revision)
    if payload.get("schema_version") != 1:
        raise ValueError("unsupported release-provenance schema version")
    if payload.get("project") != PROJECT_NAME:
        raise ValueError("release-provenance project identity is incorrect")
    source = payload.get("source")
    if source != {"repository": SOURCE_REPOSITORY, "revision": revision}:
        raise ValueError("release-provenance source identity does not match the expected revision")

    expected_image = validate_image_contract(
        inspection,
        source_revision=revision,
        image_reference=image_reference,
    )
    if payload.get("image") != expected_image:
        raise ValueError("release-provenance image identity no longer matches the inspected image")

    for section_name in ("materials", "security_evidence"):
        records = payload.get(section_name)
        if not isinstance(records, list) or not records:
            raise ValueError(f"release-provenance {section_name} must be a non-empty list")
        seen: set[str] = set()
        for record in records:
            if not isinstance(record, dict):
                raise ValueError(f"release-provenance {section_name} contains a malformed record")
            relative = str(record.get("path", ""))
            if relative in seen:
                raise ValueError(f"release-provenance {section_name} contains a duplicate path")
            seen.add(relative)
            actual = describe_file(repository_root / relative, repository_root)
            if record != actual:
                raise ValueError(f"release-provenance digest mismatch for {relative}")

    claims = payload.get("claims")
    if not isinstance(claims, dict):
        raise ValueError("release-provenance claims are missing")
    if claims.get("exact_ci_image_identity_recorded") is not True:
        raise ValueError("release-provenance must record the exact CI image identity")
    for name in (
        "deployment_performed",
        "target_environment_production_readiness_satisfied",
        "production_approved",
    ):
        if claims.get(name) is not False:
            raise ValueError(f"release-provenance claim {name} must remain false")
    if claims.get("registry_distribution_digest_recorded") != bool(expected_image["repo_digests"]):
        raise ValueError("registry-digest claim does not match the inspected image")


def command_verify(args: argparse.Namespace) -> int:
    input_path = Path(args.input)
    payload = json.loads(input_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("release-provenance input must be a JSON object")
    verify_record(
        payload,
        inspection=inspect_image(args.image_reference),
        source_revision=args.source_revision,
        image_reference=args.image_reference,
        repository_root=Path(args.repository_root).resolve(),
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    generate = subparsers.add_parser("generate", help="generate provenance JSON")
    generate.add_argument("--image-reference", required=True)
    generate.add_argument("--source-revision", required=True)
    generate.add_argument("--output", required=True)
    generate.add_argument("--repository-root", default=".")
    generate.add_argument("--material", action="append", required=True)
    generate.add_argument("--evidence", action="append", required=True)
    generate.set_defaults(handler=command_generate)

    verify = subparsers.add_parser("verify", help="verify provenance JSON against current files/image")
    verify.add_argument("--image-reference", required=True)
    verify.add_argument("--source-revision", required=True)
    verify.add_argument("--input", required=True)
    verify.add_argument("--repository-root", default=".")
    verify.set_defaults(handler=command_verify)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        return int(args.handler(args))
    except (OSError, subprocess.CalledProcessError, json.JSONDecodeError, ValueError) as exc:
        print(f"release provenance error: {type(exc).__name__}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
