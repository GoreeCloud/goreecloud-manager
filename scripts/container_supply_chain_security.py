#!/usr/bin/env python3
"""Evaluate and stamp GoreeCloud Manager container-image security evidence."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

SUPPORTED_SEVERITIES = {"UNKNOWN", "LOW", "MEDIUM", "HIGH", "CRITICAL"}
SOURCE_REVISION = re.compile(r"^[0-9a-f]{40}$")
BASE_IMAGE = re.compile(
    r"^FROM (?P<name>python):(?P<version>\d+\.\d+\.\d+)-slim@"
    r"sha256:(?P<digest>[0-9a-f]{64})$",
    re.MULTILINE,
)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def validate_source_revision(value: str) -> str:
    value = value.strip().lower()
    if SOURCE_REVISION.fullmatch(value) is None:
        raise ValueError("source revision must be a full 40-character lowercase Git commit SHA")
    return value


def parse_base_image(dockerfile: Path) -> dict[str, str]:
    text = dockerfile.read_text(encoding="utf-8")
    match = BASE_IMAGE.search(text)
    if match is None:
        raise ValueError("Dockerfile must use a patch-tagged, SHA-256-pinned python slim base image")
    data = match.groupdict()
    return {
        "reference": (
            f"{data['name']}:{data['version']}-slim@sha256:{data['digest']}"
        ),
        "python_version": data["version"],
        "digest": data["digest"],
    }


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_policy(path: Path) -> dict[str, Any]:
    policy = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(policy, dict) or policy.get("schema_version") != 1:
        raise ValueError("container vulnerability policy must use schema_version 1")

    rule = policy.get("policy")
    if not isinstance(rule, dict):
        raise ValueError("container vulnerability policy must contain a policy object")
    severities = rule.get("blocking_severities")
    if not isinstance(severities, list) or not severities:
        raise ValueError("blocking_severities must be a non-empty list")
    if (
        any(not isinstance(item, str) or item not in SUPPORTED_SEVERITIES for item in severities)
        or len(set(severities)) != len(severities)
    ):
        raise ValueError("blocking_severities contains an invalid or duplicate value")
    if rule.get("require_os_package_result") is not True:
        raise ValueError("container vulnerability policy must require an OS package result")
    for key in ("required_distro", "required_severity_source"):
        value = rule.get(key)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"container vulnerability policy must define {key}")
        rule[key] = value.strip().casefold()
    if not isinstance(policy.get("exceptions"), list):
        raise ValueError("container vulnerability exceptions must be a list")
    return policy


def validated_exceptions(
    policy: dict[str, Any], today: dt.date
) -> dict[tuple[str, str], dict[str, str]]:
    result: dict[tuple[str, str], dict[str, str]] = {}
    for item in policy["exceptions"]:
        if not isinstance(item, dict):
            raise ValueError("Every container vulnerability exception must be an object")
        required = ("vulnerability_id", "package", "expires_on", "reason")
        if any(
            not isinstance(item.get(key), str) or not item[key].strip()
            for key in required
        ):
            raise ValueError(
                "Container vulnerability exceptions require vulnerability_id, package, "
                "expires_on, and reason"
            )
        expires = dt.date.fromisoformat(item["expires_on"])
        if expires < today:
            raise ValueError(
                "Expired container vulnerability exception: "
                f"{item['vulnerability_id']} for {item['package']}"
            )
        package = item["package"].strip().casefold()
        vulnerability_id = item["vulnerability_id"].strip()
        key = (vulnerability_id, package)
        if key in result:
            raise ValueError(
                f"Duplicate container vulnerability exception: {vulnerability_id} for {package}"
            )
        result[key] = {
            "expires_on": item["expires_on"],
            "reason": item["reason"].strip(),
        }
    return result


def parse_trivy_report(path: Path) -> tuple[dict[str, Any], list[dict[str, str]], int]:
    report = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(report, dict) or report.get("SchemaVersion") != 2:
        raise ValueError("Trivy report must use JSON SchemaVersion 2")
    results = report.get("Results")
    if not isinstance(results, list):
        raise ValueError("Trivy report Results must be a list")

    os_results = [
        result
        for result in results
        if isinstance(result, dict) and result.get("Class") == "os-pkgs"
    ]
    if not os_results:
        raise ValueError("Trivy report did not contain an OS package result")

    findings: dict[tuple[str, str, str, str], dict[str, str]] = {}
    for result in os_results:
        target = result.get("Target")
        distro = result.get("Type")
        if not isinstance(target, str) or not target.strip():
            raise ValueError("Trivy OS result is missing Target")
        if not isinstance(distro, str) or not distro.strip():
            raise ValueError("Trivy OS result is missing Type")
        vulnerabilities = result.get("Vulnerabilities") or []
        if not isinstance(vulnerabilities, list):
            raise ValueError("Trivy OS vulnerabilities must be a list")
        for vulnerability in vulnerabilities:
            if not isinstance(vulnerability, dict):
                raise ValueError("Trivy vulnerability entry must be an object")
            required = ("VulnerabilityID", "PkgName", "InstalledVersion", "Severity")
            if any(
                not isinstance(vulnerability.get(key), str)
                or not vulnerability[key].strip()
                for key in required
            ):
                raise ValueError("Trivy vulnerability entry is missing required identity fields")
            severity = vulnerability["Severity"].strip().upper()
            if severity not in SUPPORTED_SEVERITIES:
                raise ValueError(f"Unsupported Trivy severity: {severity}")
            finding = {
                "vulnerability_id": vulnerability["VulnerabilityID"].strip(),
                "package": vulnerability["PkgName"].strip().casefold(),
                "installed_version": vulnerability["InstalledVersion"].strip(),
                "fixed_version": (
                    vulnerability.get("FixedVersion", "").strip()
                    if isinstance(vulnerability.get("FixedVersion", ""), str)
                    else ""
                ),
                "status": (
                    vulnerability.get("Status", "").strip()
                    if isinstance(vulnerability.get("Status", ""), str)
                    else ""
                ),
                "severity": severity,
                "severity_source": (
                    vulnerability.get("SeveritySource", "").strip().casefold()
                    if isinstance(vulnerability.get("SeveritySource", ""), str)
                    else ""
                ),
                "distro": distro.strip().casefold(),
            }
            key = (
                finding["vulnerability_id"],
                finding["package"],
                finding["installed_version"],
                finding["distro"],
            )
            findings[key] = finding

    return report, sorted(
        findings.values(),
        key=lambda item: (
            item["severity"],
            item["package"],
            item["vulnerability_id"],
            item["installed_version"],
        ),
    ), len(os_results)


def validate_scan_authority(
    findings: list[dict[str, str]], policy: dict[str, Any]
) -> None:
    required_distro = policy["policy"]["required_distro"]
    required_source = policy["policy"]["required_severity_source"]
    for finding in findings:
        if finding["distro"] != required_distro:
            raise ValueError(
                f"unexpected operating-system vulnerability source: {finding['distro']}"
            )
        if (
            finding["severity"] != "UNKNOWN"
            and finding["severity_source"] != required_source
        ):
            raise ValueError(
                "non-UNKNOWN vulnerability severity did not come from the required "
                "distribution authority"
            )


def classify(
    findings: list[dict[str, str]],
    policy: dict[str, Any],
    today: dt.date,
) -> tuple[
    list[dict[str, str]],
    list[dict[str, str]],
    list[dict[str, str]],
]:
    validate_scan_authority(findings, policy)
    exceptions = validated_exceptions(policy, today)
    blocking_severities = set(policy["policy"]["blocking_severities"])
    allowed: list[dict[str, str]] = []
    blocking: list[dict[str, str]] = []
    informational: list[dict[str, str]] = []

    for finding in findings:
        if finding["severity"] not in blocking_severities:
            informational.append(finding)
            continue
        exception = exceptions.get(
            (finding["vulnerability_id"], finding["package"].casefold())
        )
        if exception is None:
            blocking.append(finding)
        else:
            allowed.append(
                {
                    **finding,
                    "exception_expires_on": exception["expires_on"],
                    "exception_reason": exception["reason"],
                }
            )
    return allowed, blocking, informational


def stamp_sbom(
    source: Path,
    output: Path,
    *,
    source_revision: str,
    image_reference: str,
    image_id: str,
    scanner_version: str,
    base_image: dict[str, str],
) -> None:
    payload = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("bomFormat") != "CycloneDX":
        raise ValueError("container SBOM must be CycloneDX JSON")
    metadata = payload.get("metadata")
    if not isinstance(metadata, dict):
        raise ValueError("container SBOM is missing metadata")
    properties = metadata.setdefault("properties", [])
    if not isinstance(properties, list):
        raise ValueError("container SBOM metadata.properties must be a list")
    properties.extend(
        [
            {"name": "goreecloud:source-revision", "value": source_revision},
            {"name": "goreecloud:sbom-scope", "value": "built-container-image"},
            {"name": "goreecloud:image-reference", "value": image_reference},
            {"name": "goreecloud:image-id", "value": image_id},
            {"name": "goreecloud:base-image-reference", "value": base_image["reference"]},
            {"name": "goreecloud:base-image-digest", "value": base_image["digest"]},
            {"name": "goreecloud:scanner", "value": f"Trivy {scanner_version}"},
        ]
    )
    write_json(output, payload)


def command_stamp_sbom(args: argparse.Namespace) -> int:
    try:
        revision = validate_source_revision(args.source_revision)
        base_image = parse_base_image(Path(args.dockerfile))
        stamp_sbom(
            Path(args.input),
            Path(args.output),
            source_revision=revision,
            image_reference=args.image_reference.strip(),
            image_id=args.image_id.strip(),
            scanner_version=args.scanner_version.strip(),
            base_image=base_image,
        )
        print("Stamped container CycloneDX SBOM with exact Manager source identity.")
        return 0
    except Exception as exc:
        print(
            f"Container SBOM evidence could not be established; failing closed "
            f"({type(exc).__name__}).",
            file=sys.stderr,
        )
        return 2


def command_evaluate(args: argparse.Namespace) -> int:
    output = Path(args.output)
    generated_at = dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")
    try:
        revision = validate_source_revision(args.source_revision)
        raw_path = Path(args.input)
        policy = load_policy(Path(args.policy))
        base_image = parse_base_image(Path(args.dockerfile))
        _raw, findings, os_result_count = parse_trivy_report(raw_path)
        allowed, blocking, informational = classify(
            findings,
            policy,
            dt.datetime.now(dt.timezone.utc).date(),
        )
        report = {
            "schema_version": 1,
            "status": "pass" if not blocking else "fail",
            "generated_at": generated_at,
            "source_revision": revision,
            "image_reference": args.image_reference.strip(),
            "image_id": args.image_id.strip(),
            "base_image_reference": base_image["reference"],
            "base_image_digest": base_image["digest"],
            "scanner": "Trivy",
            "scanner_version": args.scanner_version.strip(),
            "trivy_report_sha256": sha256_file(raw_path),
            "os_result_count": os_result_count,
            "finding_count": len(findings),
            "allowed_finding_count": len(allowed),
            "blocking_finding_count": len(blocking),
            "informational_finding_count": len(informational),
            "policy": policy["policy"],
            "findings": findings,
            "allowed_findings": allowed,
            "blocking_findings": blocking,
            "informational_findings": informational,
        }
        write_json(output, report)
        if blocking:
            print(
                f"Container OS vulnerability evidence blocked by "
                f"{len(blocking)} distribution-authoritative HIGH/CRITICAL finding(s).",
                file=sys.stderr,
            )
            return 1
        print(
            f"Container OS vulnerability evidence passed with {len(findings)} "
            f"total finding(s) and no non-excepted distribution-authoritative "
            f"HIGH/CRITICAL findings."
        )
        return 0
    except Exception as exc:
        write_json(
            output,
            {
                "schema_version": 1,
                "status": "error",
                "generated_at": generated_at,
                "source_revision": args.source_revision,
                "scanner": "Trivy",
                "scanner_version": args.scanner_version,
                "error_type": type(exc).__name__,
                "message": (
                    "Container operating-system vulnerability evidence could not "
                    "be established; failing closed."
                ),
            },
        )
        print(
            f"Container operating-system vulnerability evidence could not be "
            f"established; failing closed ({type(exc).__name__}).",
            file=sys.stderr,
        )
        return 2


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser()
    sub = root.add_subparsers(dest="command", required=True)

    stamp = sub.add_parser("stamp-sbom")
    stamp.add_argument("--input", required=True)
    stamp.add_argument("--output", required=True)
    stamp.add_argument("--dockerfile", default="Dockerfile")
    stamp.add_argument("--source-revision", required=True)
    stamp.add_argument("--image-reference", required=True)
    stamp.add_argument("--image-id", required=True)
    stamp.add_argument("--scanner-version", required=True)
    stamp.set_defaults(func=command_stamp_sbom)

    evaluate = sub.add_parser("evaluate")
    evaluate.add_argument("--input", required=True)
    evaluate.add_argument("--policy", required=True)
    evaluate.add_argument("--output", required=True)
    evaluate.add_argument("--dockerfile", default="Dockerfile")
    evaluate.add_argument("--source-revision", required=True)
    evaluate.add_argument("--image-reference", required=True)
    evaluate.add_argument("--image-id", required=True)
    evaluate.add_argument("--scanner-version", required=True)
    evaluate.set_defaults(func=command_evaluate)
    return root


def main() -> int:
    args = parser().parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
