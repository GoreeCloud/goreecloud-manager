"""Strict read-only GoreeCloud infrastructure status contract consumer."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

STATUS_SCHEMA_VERSION = 1
MAX_STATUS_BYTES = 64 * 1024
MAX_CAPABILITIES = 32
ALLOWED_STATES = {"ready", "partial", "attention", "unavailable", "development"}
ALLOWED_CAPABILITY_STATES = {"verified", "pending", "attention", "unavailable"}
TOP_LEVEL_KEYS = {"schema_version", "producer", "generated_at", "state", "privacy", "acceptance", "capabilities"}
PRODUCER_KEYS = {"service_id", "adapter_id", "runtime_authority"}
PRIVACY_KEYS = {
    "contains_credentials",
    "contains_personal_data",
    "contains_raw_logs",
    "contains_network_identifiers",
    "contains_query_data",
    "contains_certificate_material",
}
ACCEPTANCE_KEYS = {"runtime_acceptance_required", "production_approved"}
CAPABILITY_KEYS = {"id", "state"}
SERVICE_CONFIG = {
    "goreecloud-gateway": ("GoreeCloud Gateway", "GOREECLOUD_GATEWAY_STATUS_FILE"),
    "goreecloud-dns": ("GoreeCloud DNS", "GOREECLOUD_DNS_STATUS_FILE"),
    "goreecloud-network": ("GoreeCloud Network", "GOREECLOUD_NETWORK_STATUS_FILE"),
}


@dataclass(frozen=True)
class InfrastructureCapability:
    id: str
    state: str


@dataclass(frozen=True)
class InfrastructureSnapshot:
    service_id: str
    name: str
    state: str
    detail: str
    producer: str = ""
    generated_at: str = ""
    capabilities: tuple[InfrastructureCapability, ...] = field(default_factory=tuple)
    production_approved: bool = False

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["capabilities"] = [asdict(item) for item in self.capabilities]
        return payload

    def integration_status(self) -> dict[str, str]:
        return {"state": self.state, "detail": self.detail}


def _service_name(service_id: str) -> str:
    return SERVICE_CONFIG.get(service_id, ("GoreeCloud Infrastructure", ""))[0]


def _unavailable(service_id: str, detail: str) -> InfrastructureSnapshot:
    return InfrastructureSnapshot(
        service_id=service_id,
        name=_service_name(service_id),
        state="unavailable",
        detail=detail,
    )


def _has_exact_keys(value: dict[str, Any], expected: set[str]) -> bool:
    return set(value) == expected


def _valid_utc_timestamp(value: Any) -> bool:
    if not isinstance(value, str) or not value.endswith("Z"):
        return False
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError:
        return False
    return parsed.tzinfo == timezone.utc


def _validate(service_id: str, payload: Any) -> InfrastructureSnapshot:
    name = _service_name(service_id)
    if not isinstance(payload, dict):
        return _unavailable(service_id, f"{name} status is not a JSON object.")
    if not _has_exact_keys(payload, TOP_LEVEL_KEYS):
        return _unavailable(service_id, f"{name} status contains missing or unapproved top-level fields.")
    if payload.get("schema_version") != STATUS_SCHEMA_VERSION:
        return _unavailable(service_id, f"{name} status uses an unsupported contract version.")

    producer = payload.get("producer")
    if not isinstance(producer, dict) or not _has_exact_keys(producer, PRODUCER_KEYS):
        return _unavailable(service_id, f"{name} status has malformed producer metadata.")
    if producer.get("service_id") != service_id:
        return _unavailable(service_id, f"{name} status producer identity does not match the configured service.")
    adapter_id = producer.get("adapter_id")
    runtime_authority = producer.get("runtime_authority")
    if not isinstance(adapter_id, str) or not adapter_id.strip():
        return _unavailable(service_id, f"{name} status has invalid adapter identity.")
    if not isinstance(runtime_authority, str) or not runtime_authority.startswith("GoreeCloud/"):
        return _unavailable(service_id, f"{name} status has invalid runtime authority.")

    generated_at = payload.get("generated_at")
    if not _valid_utc_timestamp(generated_at):
        return _unavailable(service_id, f"{name} status has an invalid UTC generation timestamp.")

    state = payload.get("state")
    if state not in ALLOWED_STATES:
        return _unavailable(service_id, f"{name} status has an unsupported state.")

    privacy = payload.get("privacy")
    if not isinstance(privacy, dict) or not _has_exact_keys(privacy, PRIVACY_KEYS):
        return _unavailable(service_id, f"{name} status has malformed privacy guarantees.")
    for guarantee in PRIVACY_KEYS:
        if privacy.get(guarantee) is not False:
            return _unavailable(service_id, f"{name} status was rejected because sensitive infrastructure content is present or undeclared.")

    acceptance = payload.get("acceptance")
    if not isinstance(acceptance, dict) or not _has_exact_keys(acceptance, ACCEPTANCE_KEYS):
        return _unavailable(service_id, f"{name} status has malformed acceptance metadata.")
    if acceptance.get("runtime_acceptance_required") is not True:
        return _unavailable(service_id, f"{name} status must preserve the runtime acceptance boundary.")
    production_approved = acceptance.get("production_approved")
    if not isinstance(production_approved, bool):
        return _unavailable(service_id, f"{name} status has invalid production approval state.")

    rows = payload.get("capabilities")
    if not isinstance(rows, list) or not rows or len(rows) > MAX_CAPABILITIES:
        return _unavailable(service_id, f"{name} status capabilities are malformed or outside the approved bound.")
    capabilities: list[InfrastructureCapability] = []
    seen: set[str] = set()
    for row in rows:
        if not isinstance(row, dict) or not _has_exact_keys(row, CAPABILITY_KEYS):
            return _unavailable(service_id, f"{name} capability status contains malformed or unapproved fields.")
        capability_id = row.get("id")
        capability_state = row.get("state")
        if not isinstance(capability_id, str) or not capability_id or capability_id in seen:
            return _unavailable(service_id, f"{name} capability identity is missing or duplicated.")
        if capability_state not in ALLOWED_CAPABILITY_STATES:
            return _unavailable(service_id, f"{name} capability status is unsupported.")
        seen.add(capability_id)
        capabilities.append(InfrastructureCapability(id=capability_id, state=capability_state))

    detail = f"{name} supplied an accepted privacy-minimized status document with {len(capabilities)} capability state(s)."
    return InfrastructureSnapshot(
        service_id=service_id,
        name=name,
        state=state,
        detail=detail,
        producer=runtime_authority,
        generated_at=generated_at,
        capabilities=tuple(capabilities),
        production_approved=production_approved,
    )


def infrastructure_snapshot(service_id: str) -> InfrastructureSnapshot:
    """Load one approved local status document without service credentials or network access."""
    config = SERVICE_CONFIG.get(service_id)
    if config is None:
        return _unavailable(service_id, "Unknown GoreeCloud infrastructure service identity.")
    name, env_name = config
    raw_path = os.getenv(env_name, "").strip()
    if not raw_path:
        return _unavailable(service_id, f"{name} status is disabled until {env_name} points to an approved sanitized status document.")
    path = Path(raw_path)
    try:
        if not path.is_file():
            return _unavailable(service_id, f"Configured {name} status file is unavailable.")
        if path.stat().st_size > MAX_STATUS_BYTES:
            return _unavailable(service_id, f"Configured {name} status file exceeds the approved size bound.")
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return _unavailable(service_id, f"Configured {name} status file could not be safely read.")
    return _validate(service_id, payload)


def gateway_snapshot() -> InfrastructureSnapshot:
    return infrastructure_snapshot("goreecloud-gateway")


def dns_snapshot() -> InfrastructureSnapshot:
    return infrastructure_snapshot("goreecloud-dns")


def network_snapshot() -> InfrastructureSnapshot:
    return infrastructure_snapshot("goreecloud-network")
