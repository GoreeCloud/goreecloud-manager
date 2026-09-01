"""Strict read-only GoreeCloud infrastructure status contract consumer."""

from __future__ import annotations

import json
import os
import stat
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

STATUS_SCHEMA_VERSION = 1
MAX_STATUS_BYTES = 64 * 1024
MAX_CAPABILITIES = 32
MAX_STATUS_AGE = timedelta(minutes=5)
MAX_FUTURE_SKEW = timedelta(seconds=30)
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
EXPECTED_PRODUCERS = {
    "goreecloud-gateway": ("goreecloud-gateway/status-v1", "GoreeCloud/CaddyDataPlane"),
    "goreecloud-dns": ("goreecloud-dns/status-v1", "GoreeCloud/AdGuardHomeDataPlane"),
    "goreecloud-network": ("goreecloud-network/status-v1", "GoreeCloud/NetBirdDataPlane"),
}
EXPECTED_CAPABILITY_IDS = {
    "goreecloud-gateway": {"ingress", "https", "certificates", "publication"},
    "goreecloud-dns": {"resolver", "filtering", "encrypted-dns", "dns-policy"},
    "goreecloud-network": {"private-connectivity", "peer-coordination", "access-policy", "network-dns"},
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


def _parse_utc_timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.endswith("Z"):
        return None
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError:
        return None
    if parsed.tzinfo != timezone.utc:
        return None
    return parsed


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
    expected_adapter_id, expected_runtime_authority = EXPECTED_PRODUCERS[service_id]
    adapter_id = producer.get("adapter_id")
    runtime_authority = producer.get("runtime_authority")
    if adapter_id != expected_adapter_id:
        return _unavailable(service_id, f"{name} status adapter identity does not match the approved producer contract.")
    if runtime_authority != expected_runtime_authority:
        return _unavailable(service_id, f"{name} status runtime authority does not match the approved producer contract.")

    generated_at = payload.get("generated_at")
    generated = _parse_utc_timestamp(generated_at)
    if generated is None:
        return _unavailable(service_id, f"{name} status has an invalid UTC generation timestamp.")
    now = datetime.now(timezone.utc)
    if generated > now + MAX_FUTURE_SKEW:
        return _unavailable(service_id, f"{name} status generation timestamp is unacceptably far in the future.")
    if generated < now - MAX_STATUS_AGE:
        return _unavailable(service_id, f"{name} status is stale and has failed closed.")

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
    if seen != EXPECTED_CAPABILITY_IDS[service_id]:
        return _unavailable(service_id, f"{name} capability inventory does not match the approved Infrastructure Status v1 contract.")

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
        with path.open("rb") as handle:
            mode = os.fstat(handle.fileno()).st_mode
            if not stat.S_ISREG(mode):
                return _unavailable(service_id, f"Configured {name} status file is unavailable.")
            raw = handle.read(MAX_STATUS_BYTES + 1)
        if len(raw) > MAX_STATUS_BYTES:
            return _unavailable(service_id, f"Configured {name} status file exceeds the approved size bound.")
        payload = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return _unavailable(service_id, f"Configured {name} status file could not be safely read.")
    return _validate(service_id, payload)


def gateway_snapshot() -> InfrastructureSnapshot:
    return infrastructure_snapshot("goreecloud-gateway")


def dns_snapshot() -> InfrastructureSnapshot:
    return infrastructure_snapshot("goreecloud-dns")


def network_snapshot() -> InfrastructureSnapshot:
    return infrastructure_snapshot("goreecloud-network")
