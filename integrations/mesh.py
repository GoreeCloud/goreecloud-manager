"""Read-only GoreeCloud Mesh platform-registry integration for Manager.

Manager consumes only normalized Mesh platform records and never receives registry write
scope. Mesh transport authentication proves the upstream service boundary; producer
systems and the canonical evaluator remain authoritative for the facts represented by
each record.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx

DEFAULT_TIMEOUT_SECONDS = 5.0
MAX_TIMEOUT_SECONDS = 30.0
PLATFORM_REGISTRY_PATH = "/v1/platform-registry"
EXPECTED_RECORD_SCHEMA = "goreecloud.mesh.platform-record.v1"
EXPECTED_CONTRACT_SCHEMA = "0.2"
EXPECTED_EVALUATOR_REPOSITORY = "GoreeCloud/GoreeCloud"
MAX_RESPONSE_BYTES = 1 << 20
PLATFORM_SYSTEM_KEYS = (
    "manager",
    "identity",
    "wardveil_security",
    "privacy_shield",
    "everkeep",
    "mesh",
    "glaze_ui",
)
LIFECYCLES = {
    "concept",
    "experimental",
    "development",
    "release-candidate",
    "stable",
    "deprecated",
    "retired",
}
PLATFORM_RESULTS = {
    "applicable-conformant",
    "applicable-migration-required",
    "applicable-blocked",
    "applicable-nonconformant",
    "not-applicable-justified",
}
CONFORMANCE_RESULTS = {"conformant", "nonconformant", "unverified"}
VERIFICATION_STATES = {
    "verified",
    "implemented_unverified",
    "required_missing",
    "not_applicable",
    "unknown",
}
COMPONENT_ID_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
REVISION_PATTERN = re.compile(r"^[0-9a-f]{40}$")


@dataclass(frozen=True)
class MeshRelationship:
    target: str
    relationship_type: str
    required: bool


@dataclass(frozen=True)
class MeshPlatformRecord:
    component_id: str
    product_name: str
    kind: str
    lifecycle: str
    version: str
    supported_platforms: tuple[str, ...]
    repository: str
    source_revision: str
    capabilities: tuple[str, ...]
    dependencies: tuple[str, ...]
    relationships: tuple[MeshRelationship, ...]
    platform_systems: tuple[tuple[str, str], ...]
    runtime_state: str
    health_state: str
    readiness: str
    backup_status: str
    restore_status: str
    last_verified_restore: datetime | None
    export_status: str
    export_formats: tuple[str, ...]
    declared_result: str
    computed_result: str
    stable_eligible: bool
    evaluator_repository: str
    evaluator_revision: str
    evaluated_at: datetime
    missing_mandatory_evidence: tuple[str, ...]
    blockers: tuple[str, ...]
    observed_at: datetime

    @property
    def platform_system_map(self) -> dict[str, str]:
        return dict(self.platform_systems)

    @property
    def overall_result(self) -> str:
        """Compatibility alias while the Platform page migrates its display vocabulary."""

        return self.computed_result

    @property
    def continuity_verified(self) -> bool:
        return self.restore_status == "verified" and self.last_verified_restore is not None


@dataclass(frozen=True)
class MeshPlatformSnapshot:
    state: str
    detail: str
    condition: str = "unknown"
    records: tuple[MeshPlatformRecord, ...] = ()

    def integration_status(self) -> dict[str, str]:
        return {"state": self.state, "detail": self.detail}

    @property
    def conformant_count(self) -> int:
        return sum(record.computed_result == "conformant" for record in self.records)

    @property
    def stable_eligible_count(self) -> int:
        return sum(record.stable_eligible for record in self.records)

    @property
    def verified_restore_count(self) -> int:
        return sum(record.continuity_verified for record in self.records)

    @property
    def relationship_count(self) -> int:
        return sum(len(record.dependencies) + len(record.relationships) for record in self.records)


class MeshProtocolError(ValueError):
    """Raised when Mesh returns data Manager cannot safely normalize."""


def _enabled() -> bool:
    return os.getenv("MESH_ENABLED", "false").strip().lower() in {"1", "true", "yes", "on"}


def _timeout_seconds() -> float:
    raw = os.getenv("MESH_TIMEOUT_SECONDS", str(DEFAULT_TIMEOUT_SECONDS)).strip()
    try:
        value = float(raw)
    except ValueError:
        return DEFAULT_TIMEOUT_SECONDS
    if value <= 0:
        return DEFAULT_TIMEOUT_SECONDS
    return min(value, MAX_TIMEOUT_SECONDS)


def _configured_token() -> tuple[str | None, str | None]:
    direct = os.getenv("MESH_ACCESS_TOKEN", "").strip()
    file_path = os.getenv("MESH_ACCESS_TOKEN_FILE", "").strip()
    if direct and file_path:
        return None, "Set only one Mesh access-token source."
    if file_path:
        try:
            token = Path(file_path).read_text(encoding="utf-8").strip()
        except OSError:
            return None, "The configured Mesh access-token file could not be read."
        if not token:
            return None, "The configured Mesh access-token file is empty."
        return token, None
    if direct:
        return direct, None
    return None, "Missing MESH_ACCESS_TOKEN or MESH_ACCESS_TOKEN_FILE."


def _api_url() -> tuple[str | None, str | None]:
    base_url = os.getenv("MESH_API_URL", "").strip().rstrip("/")
    if not base_url:
        return None, "Missing MESH_API_URL."
    parsed = urlparse(base_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None, "MESH_API_URL must be an absolute HTTP(S) URL."
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        return None, "MESH_API_URL must not embed credentials, query parameters, or fragments."
    return f"{base_url}{PLATFORM_REGISTRY_PATH}", None


def _mapping(value: Any, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise MeshProtocolError(f"Mesh returned an invalid {field} object.")
    return value


def _text(value: Any, field: str, *, required: bool = True) -> str:
    if value is None:
        value = ""
    if not isinstance(value, str):
        raise MeshProtocolError(f"Mesh returned an invalid {field} value.")
    value = value.strip()
    if required and not value:
        raise MeshProtocolError(f"Mesh returned a blank required {field} value.")
    return value


def _text_list(value: Any, field: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list):
        raise MeshProtocolError(f"Mesh returned an invalid {field} list.")
    normalized = tuple(_text(item, field) for item in value)
    if len(set(normalized)) != len(normalized):
        raise MeshProtocolError(f"Mesh returned duplicate {field} values.")
    return normalized


def _timestamp(value: Any, field: str, *, required: bool = True) -> datetime | None:
    if value is None and not required:
        return None
    text = _text(value, field)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise MeshProtocolError(f"Mesh returned an invalid {field} timestamp.") from exc
    if parsed.tzinfo is None:
        raise MeshProtocolError(f"Mesh returned {field} without a timezone.")
    return parsed


def _component_id(value: Any, field: str) -> str:
    text = _text(value, field)
    if not COMPONENT_ID_PATTERN.fullmatch(text):
        raise MeshProtocolError(f"Mesh returned an invalid {field} value.")
    return text


def _revision(value: Any, field: str) -> str:
    text = _text(value, field)
    if not REVISION_PATTERN.fullmatch(text):
        raise MeshProtocolError(f"Mesh returned an invalid {field} Git revision.")
    return text


def _relationship(raw: Any) -> MeshRelationship:
    value = _mapping(raw, "relationship")
    required = value.get("required")
    if not isinstance(required, bool):
        raise MeshProtocolError("Mesh returned an invalid relationship required flag.")
    return MeshRelationship(
        target=_component_id(value.get("target"), "relationship target"),
        relationship_type=_text(value.get("type"), "relationship type"),
        required=required,
    )


def _record(raw: Any) -> MeshPlatformRecord:
    value = _mapping(raw, "platform record")
    if value.get("schema") != EXPECTED_RECORD_SCHEMA:
        raise MeshProtocolError("Mesh returned an unsupported platform-record schema.")

    source = _mapping(value.get("source"), "source")
    component = _mapping(value.get("component"), "component")
    systems = _mapping(value.get("platform_systems"), "platform systems")
    health = _mapping(value.get("health"), "health")
    recovery = _mapping(value.get("recovery"), "recovery")
    portability = _mapping(value.get("portability"), "portability")
    conformance = _mapping(value.get("conformance"), "conformance")

    repository = _text(component.get("repository"), "component repository")
    if _text(source.get("repository"), "source repository") != repository:
        raise MeshProtocolError("Mesh returned a platform record with mismatched source authority.")
    if source.get("authority_transfer") is not False:
        raise MeshProtocolError("Mesh returned a platform record that requested authority transfer.")
    if source.get("contract_schema_version") != EXPECTED_CONTRACT_SCHEMA:
        raise MeshProtocolError("Mesh returned an unsupported Platform Contract schema version.")
    source_revision = _revision(source.get("revision"), "source revision")

    component_id = _component_id(component.get("id"), "component id")
    kind = _text(component.get("kind"), "component kind")
    if kind not in {"application", "service"}:
        raise MeshProtocolError("Mesh returned an unsupported component kind.")
    lifecycle = _text(component.get("lifecycle"), "lifecycle")
    if lifecycle not in LIFECYCLES:
        raise MeshProtocolError("Mesh returned an unsupported lifecycle state.")

    if set(systems) != set(PLATFORM_SYSTEM_KEYS):
        raise MeshProtocolError("Mesh returned an incomplete or extended Platform System set.")
    normalized_systems: list[tuple[str, str]] = []
    for key in PLATFORM_SYSTEM_KEYS:
        system = _mapping(systems.get(key), f"{key} platform-system")
        result = _text(system.get("result"), f"{key} result")
        if result not in PLATFORM_RESULTS:
            raise MeshProtocolError("Mesh returned an unsupported Platform System result.")
        normalized_systems.append((key, result))

    backup_status = _text(recovery.get("backup_status"), "backup status")
    restore_status = _text(recovery.get("restore_status"), "restore status")
    export_status = _text(portability.get("export_status"), "export status")
    if any(state not in VERIFICATION_STATES for state in (backup_status, restore_status, export_status)):
        raise MeshProtocolError("Mesh returned an unsupported verification state.")
    last_verified_restore = _timestamp(
        recovery.get("last_verified_restore"),
        "last verified restore",
        required=False,
    )
    if restore_status == "verified" and last_verified_restore is None:
        raise MeshProtocolError("Mesh returned verified restore state without restore evidence time.")
    if restore_status != "verified" and last_verified_restore is not None:
        raise MeshProtocolError("Mesh returned a restore evidence time for a non-verified restore state.")

    declared_result = _text(conformance.get("declared_result"), "declared conformance result")
    computed_result = _text(conformance.get("computed_result"), "computed conformance result")
    if declared_result not in CONFORMANCE_RESULTS or computed_result not in CONFORMANCE_RESULTS:
        raise MeshProtocolError("Mesh returned an unsupported conformance result.")
    stable_eligible = conformance.get("stable_eligible")
    if not isinstance(stable_eligible, bool):
        raise MeshProtocolError("Mesh returned an invalid Stable-eligibility value.")
    if computed_result != "conformant" and stable_eligible:
        raise MeshProtocolError("Mesh returned nonconformant or unverified state as Stable-eligible.")
    if lifecycle == "stable" and (computed_result != "conformant" or not stable_eligible):
        raise MeshProtocolError("Mesh returned a Stable lifecycle record without current Stable eligibility.")

    evaluator_repository = _text(conformance.get("evaluator_repository"), "evaluator repository")
    if evaluator_repository != EXPECTED_EVALUATOR_REPOSITORY:
        raise MeshProtocolError("Mesh returned conformance from a non-canonical evaluator.")
    evaluator_revision = _revision(conformance.get("evaluator_revision"), "evaluator revision")
    evaluated_at = _timestamp(conformance.get("evaluated_at"), "evaluated at")

    dependencies = _text_list(value.get("dependencies", []), "dependency")
    for dependency in dependencies:
        _component_id(dependency, "dependency")

    relationships_raw = value.get("relationships", [])
    if not isinstance(relationships_raw, list):
        raise MeshProtocolError("Mesh returned an invalid relationships list.")

    return MeshPlatformRecord(
        component_id=component_id,
        product_name=_text(component.get("product_name"), "product name"),
        kind=kind,
        lifecycle=lifecycle,
        version=_text(component.get("version"), "component version"),
        supported_platforms=_text_list(component.get("supported_platforms"), "supported platform"),
        repository=repository,
        source_revision=source_revision,
        capabilities=_text_list(value.get("capabilities", []), "capability"),
        dependencies=dependencies,
        relationships=tuple(_relationship(item) for item in relationships_raw),
        platform_systems=tuple(normalized_systems),
        runtime_state=_text(health.get("runtime_state"), "runtime state"),
        health_state=_text(health.get("health_state"), "health state"),
        readiness=_text(health.get("readiness"), "readiness"),
        backup_status=backup_status,
        restore_status=restore_status,
        last_verified_restore=last_verified_restore,
        export_status=export_status,
        export_formats=_text_list(portability.get("formats", []), "export format"),
        declared_result=declared_result,
        computed_result=computed_result,
        stable_eligible=stable_eligible,
        evaluator_repository=evaluator_repository,
        evaluator_revision=evaluator_revision,
        evaluated_at=evaluated_at,
        missing_mandatory_evidence=_text_list(
            conformance.get("missing_mandatory_evidence", []),
            "missing mandatory evidence",
        ),
        blockers=_text_list(conformance.get("blockers", []), "conformance blocker"),
        observed_at=_timestamp(value.get("observed_at"), "observed at"),
    )


def _healthy_snapshot(payload: Any) -> MeshPlatformSnapshot:
    value = _mapping(payload, "platform registry response")
    records_raw = value.get("records")
    count = value.get("count")
    if not isinstance(records_raw, list) or isinstance(count, bool) or not isinstance(count, int):
        raise MeshProtocolError("Mesh returned an incomplete platform registry response.")
    if count < 0 or count != len(records_raw):
        raise MeshProtocolError("Mesh returned inconsistent platform registry counts.")
    records = tuple(sorted((_record(item) for item in records_raw), key=lambda item: item.component_id))
    if len({item.component_id for item in records}) != len(records):
        raise MeshProtocolError("Mesh returned duplicate component records.")
    return MeshPlatformSnapshot(
        state="healthy",
        detail=f"Live authority-preserving Mesh platform registry data verified for {count} component(s).",
        condition="healthy",
        records=records,
    )


def mesh_platform_snapshot() -> MeshPlatformSnapshot:
    """Return Manager's normalized, read-only view of the Mesh platform registry."""

    if not _enabled():
        return MeshPlatformSnapshot(
            state="disabled",
            detail="Disabled until the scoped GoreeCloud Mesh read integration is explicitly enabled.",
            condition="disabled",
        )

    api_url, url_error = _api_url()
    token, token_error = _configured_token()
    configuration_errors = [error for error in (url_error, token_error) if error]
    if configuration_errors:
        return MeshPlatformSnapshot(
            state="misconfigured",
            detail=" ".join(configuration_errors),
            condition="misconfigured",
        )

    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {token}",
        "User-Agent": "goreecloud-manager/0.1",
    }
    try:
        response = httpx.get(api_url, headers=headers, timeout=_timeout_seconds())
    except httpx.TimeoutException:
        return MeshPlatformSnapshot(
            state="unavailable",
            detail="GoreeCloud Mesh did not respond before the configured timeout.",
            condition="unreachable",
        )
    except httpx.RequestError:
        return MeshPlatformSnapshot(
            state="unavailable",
            detail="Manager could not reach the configured GoreeCloud Mesh API endpoint.",
            condition="unreachable",
        )

    if response.status_code == 401:
        return MeshPlatformSnapshot(
            state="unavailable",
            detail="GoreeCloud Mesh rejected the configured service credential.",
            condition="authentication-rejected",
        )
    if response.status_code == 403:
        return MeshPlatformSnapshot(
            state="unavailable",
            detail="GoreeCloud Mesh denied the configured read-only platform-registry request.",
            condition="authorization-denied",
        )
    if response.status_code == 404:
        return MeshPlatformSnapshot(
            state="unavailable",
            detail="The configured GoreeCloud Mesh platform-registry endpoint is not available.",
            condition="endpoint-unavailable",
        )
    try:
        response.raise_for_status()
    except httpx.HTTPStatusError:
        return MeshPlatformSnapshot(
            state="unavailable",
            detail=f"GoreeCloud Mesh API returned HTTP {response.status_code}.",
            condition="upstream-error",
        )

    if len(response.content) > MAX_RESPONSE_BYTES:
        return MeshPlatformSnapshot(
            state="unavailable",
            detail="GoreeCloud Mesh returned a response larger than Manager's approved platform-registry bound.",
            condition="response-too-large",
        )
    try:
        return _healthy_snapshot(response.json())
    except (ValueError, MeshProtocolError, TypeError):
        return MeshPlatformSnapshot(
            state="unavailable",
            detail="GoreeCloud Mesh returned a response Manager could not safely interpret.",
            condition="schema-invalid",
        )
