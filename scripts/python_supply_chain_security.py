#!/usr/bin/env python3
"""Generate Python dependency SBOMs and fail-closed OSV vulnerability evidence."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import sys
import time
import urllib.parse
import urllib.request
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

OSV_QUERY_BATCH_URL = "https://api.osv.dev/v1/querybatch"
LOCK_ENTRY = re.compile(
    r"^(?P<name>[A-Za-z0-9_.-]+)==(?P<version>[^\s\\]+)\s+"
    r"--hash=sha256:(?P<sha256>[0-9a-f]{64})$"
)
MAX_OSV_RESPONSE_BYTES = 4 * 1024 * 1024


@dataclass(frozen=True)
class LockedPackage:
    name: str
    version: str
    sha256: str

    @property
    def normalized_name(self) -> str:
        return re.sub(r"[-_.]+", "-", self.name).lower()

    @property
    def purl(self) -> str:
        name = urllib.parse.quote(self.normalized_name, safe="-._~")
        version = urllib.parse.quote(self.version, safe="-._~+")
        return f"pkg:pypi/{name}@{version}"


def logical_lock_lines(text: str) -> list[str]:
    result: list[str] = []
    pending = ""
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        pending = f"{pending} {line}".strip()
        if pending.endswith("\\"):
            pending = pending[:-1].rstrip()
            continue
        result.append(pending)
        pending = ""
    if pending:
        raise ValueError("requirements.lock has an incomplete continuation")
    return result


def parse_lock(path: Path) -> list[LockedPackage]:
    packages: list[LockedPackage] = []
    seen: set[str] = set()
    for line in logical_lock_lines(path.read_text(encoding="utf-8")):
        match = LOCK_ENTRY.fullmatch(line)
        if match is None:
            raise ValueError(f"Unsupported requirements.lock entry: {line!r}")
        package = LockedPackage(**match.groupdict())
        if package.normalized_name in seen:
            raise ValueError(f"Duplicate locked package: {package.name}")
        seen.add(package.normalized_name)
        packages.append(package)
    if not packages:
        raise ValueError("requirements.lock contains no packages")
    return packages


def lock_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_sbom(
    packages: list[LockedPackage], source_revision: str, lock_digest: str
) -> dict[str, Any]:
    source_revision = source_revision.strip()
    if not source_revision:
        raise ValueError("source revision must not be empty")
    root_ref = f"goreecloud-manager@{source_revision}"
    serial = uuid.uuid5(
        uuid.NAMESPACE_URL,
        "https://github.com/GoreeCloud/goreecloud-manager"
        f"#python-runtime:{source_revision}:{lock_digest}",
    )
    components = [
        {
            "bom-ref": package.purl,
            "type": "library",
            "name": package.name,
            "version": package.version,
            "hashes": [{"alg": "SHA-256", "content": package.sha256}],
            "purl": package.purl,
        }
        for package in packages
    ]
    return {
        "$schema": "https://cyclonedx.org/schema/bom-1.7.schema.json",
        "bomFormat": "CycloneDX",
        "specVersion": "1.7",
        "serialNumber": f"urn:uuid:{serial}",
        "version": 1,
        "metadata": {
            "component": {
                "bom-ref": root_ref,
                "type": "application",
                "name": "goreecloud-manager",
                "version": source_revision,
            },
            "properties": [
                {"name": "goreecloud:python-lock-sha256", "value": lock_digest},
                {
                    "name": "goreecloud:sbom-scope",
                    "value": "python-runtime-dependencies",
                },
            ],
        },
        "components": components,
        "dependencies": [
            {"ref": root_ref, "dependsOn": [package.purl for package in packages]}
        ],
    }


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def post_osv(payload: dict[str, Any], timeout: float, attempts: int) -> dict[str, Any]:
    body = json.dumps(payload, separators=(",", ":")).encode()
    request = urllib.request.Request(
        OSV_QUERY_BATCH_URL,
        data=body,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "goreecloud-manager-security-evidence/1",
        },
        method="POST",
    )
    last_error: BaseException | None = None
    for attempt in range(attempts):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                raw = response.read(MAX_OSV_RESPONSE_BYTES + 1)
            if len(raw) > MAX_OSV_RESPONSE_BYTES:
                raise RuntimeError("OSV response exceeded local safety limit")
            decoded = json.loads(raw.decode())
            if not isinstance(decoded, dict):
                raise RuntimeError("OSV returned non-object JSON")
            return decoded
        except Exception as exc:  # fail closed after bounded retries
            last_error = exc
            if attempt + 1 < attempts:
                time.sleep(min(2**attempt, 2))
    raise RuntimeError("OSV request failed after bounded retries") from last_error


def query_osv(
    packages: list[LockedPackage], timeout: float = 10.0, attempts: int = 2
) -> list[dict[str, str]]:
    response = post_osv(
        {
            "queries": [
                {
                    "package": {"ecosystem": "PyPI", "name": package.name},
                    "version": package.version,
                }
                for package in packages
            ]
        },
        timeout,
        attempts,
    )
    results = response.get("results")
    if not isinstance(results, list) or len(results) != len(packages):
        raise RuntimeError("OSV response did not match query ordering")
    findings: dict[tuple[str, str, str], dict[str, str]] = {}
    for package, result in zip(packages, results, strict=True):
        if not isinstance(result, dict) or result.get("next_page_token"):
            raise RuntimeError("OSV response is invalid or paginated; evidence is incomplete")
        vulns = result.get("vulns", [])
        if not isinstance(vulns, list):
            raise RuntimeError("OSV vulnerability list is invalid")
        for vuln in vulns:
            if not isinstance(vuln, dict) or not isinstance(vuln.get("id"), str):
                raise RuntimeError("OSV vulnerability entry is invalid")
            finding = {
                "package": package.normalized_name,
                "version": package.version,
                "osv_id": vuln["id"],
                "modified": vuln.get("modified", ""),
            }
            findings[(finding["package"], finding["version"], finding["osv_id"])] = finding
    return sorted(
        findings.values(),
        key=lambda item: (item["package"], item["version"], item["osv_id"]),
    )


def load_policy(path: Path) -> dict[str, Any]:
    policy = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(policy, dict) or policy.get("schema_version") != 1:
        raise ValueError("OSV policy must use schema_version 1")
    rule = policy.get("policy")
    if not isinstance(rule, dict) or rule.get("fail_on_any_known_vulnerability") is not True:
        raise ValueError("OSV policy must fail on every non-excepted finding")
    if not isinstance(policy.get("exceptions"), list):
        raise ValueError("OSV policy exceptions must be a list")
    return policy


def validated_exceptions(policy: dict[str, Any], today: dt.date) -> dict[tuple[str, str], dict[str, str]]:
    result: dict[tuple[str, str], dict[str, str]] = {}
    for item in policy["exceptions"]:
        if not isinstance(item, dict):
            raise ValueError("Every OSV exception must be an object")
        required = ("osv_id", "package", "expires_on", "reason")
        if any(not isinstance(item.get(key), str) or not item[key].strip() for key in required):
            raise ValueError("OSV exceptions require osv_id, package, expires_on, and reason")
        expires = dt.date.fromisoformat(item["expires_on"])
        if expires < today:
            raise ValueError(f"Expired OSV exception: {item['osv_id']} for {item['package']}")
        package = re.sub(r"[-_.]+", "-", item["package"]).lower()
        key = (item["osv_id"], package)
        if key in result:
            raise ValueError(f"Duplicate OSV exception: {key[0]} for {key[1]}")
        result[key] = {
            "expires_on": item["expires_on"],
            "reason": item["reason"].strip(),
        }
    return result


def classify(
    findings: list[dict[str, str]], policy: dict[str, Any], today: dt.date
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    exceptions = validated_exceptions(policy, today)
    allowed: list[dict[str, str]] = []
    blocking: list[dict[str, str]] = []
    for finding in findings:
        exception = exceptions.get((finding["osv_id"], finding["package"]))
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
    return allowed, blocking


def command_sbom(args: argparse.Namespace) -> int:
    lock = Path(args.lock)
    packages = parse_lock(lock)
    write_json(Path(args.output), build_sbom(packages, args.source_revision, lock_sha256(lock)))
    print(f"Generated CycloneDX SBOM for {len(packages)} locked Python packages.")
    return 0


def command_scan(args: argparse.Namespace) -> int:
    output = Path(args.output)
    generated_at = dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")
    try:
        lock = Path(args.lock)
        packages = parse_lock(lock)
        policy = load_policy(Path(args.policy))
        findings = query_osv(packages, args.timeout_seconds, args.attempts)
        allowed, blocking = classify(findings, policy, dt.datetime.now(dt.timezone.utc).date())
        report = {
            "schema_version": 1,
            "status": "pass" if not blocking else "fail",
            "generated_at": generated_at,
            "source_revision": args.source_revision,
            "database": "OSV.dev",
            "api": OSV_QUERY_BATCH_URL,
            "ecosystem": "PyPI",
            "lock_sha256": lock_sha256(lock),
            "package_count": len(packages),
            "finding_count": len(findings),
            "allowed_finding_count": len(allowed),
            "blocking_finding_count": len(blocking),
            "policy": policy["policy"],
            "findings": findings,
            "allowed_findings": allowed,
            "blocking_findings": blocking,
        }
        write_json(output, report)
        if blocking:
            print(f"OSV scan blocked by {len(blocking)} known vulnerability finding(s).", file=sys.stderr)
            return 1
        print(f"OSV scan passed for {len(packages)} locked Python packages.")
        return 0
    except Exception as exc:
        write_json(
            output,
            {
                "schema_version": 1,
                "status": "error",
                "generated_at": generated_at,
                "source_revision": args.source_revision,
                "database": "OSV.dev",
                "api": OSV_QUERY_BATCH_URL,
                "error_type": type(exc).__name__,
                "message": "Vulnerability evidence could not be established; failing closed.",
            },
        )
        print(
            f"Vulnerability evidence could not be established; failing closed ({type(exc).__name__}).",
            file=sys.stderr,
        )
        return 2


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser()
    sub = root.add_subparsers(dest="command", required=True)
    sbom = sub.add_parser("sbom")
    sbom.add_argument("--lock", default="requirements.lock")
    sbom.add_argument("--output", required=True)
    sbom.add_argument("--source-revision", required=True)
    sbom.set_defaults(func=command_sbom)
    scan = sub.add_parser("scan")
    scan.add_argument("--lock", default="requirements.lock")
    scan.add_argument("--policy", required=True)
    scan.add_argument("--output", required=True)
    scan.add_argument("--source-revision", required=True)
    scan.add_argument("--timeout-seconds", type=float, default=10.0)
    scan.add_argument("--attempts", type=int, default=2)
    scan.set_defaults(func=command_scan)
    return root


def main() -> int:
    args = parser().parse_args()
    if getattr(args, "timeout_seconds", 1.0) <= 0:
        raise SystemExit("--timeout-seconds must be positive")
    if not 1 <= getattr(args, "attempts", 1) <= 3:
        raise SystemExit("--attempts must be between 1 and 3")
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
