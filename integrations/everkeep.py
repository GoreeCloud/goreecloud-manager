"""Privacy-safe GoreeCloud Everkeep resilience status integration boundary."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

STATUS_SCHEMA_VERSION = 1
ALLOWED_STATES = {"ready", "partial", "attention", "unavailable", "development"}
ALLOWED_CAPABILITY_STATES = {"verified", "pending", "attention", "unavailable"}


@dataclass(frozen=True)
class EverkeepCapability:
    id: str
    state: str


@dataclass(frozen=True)
class EverkeepSnapshot:
    state: str
    detail: str
    producer: str = ""
    generated_at: str = ""
    recovery_readiness: str = "unavailable"
    backup_verification: str = "unavailable"
    portability_continuity: str = "unavailable"
    preservation: str = "unavailable"
    capabilities: tuple[EverkeepCapability, ...] = field(default_factory=tuple)
    production_approved: bool = False

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["capabilities"] = [asdict(item) for item in self.capabilities]
        return payload


def _unavailable(detail: str) -> EverkeepSnapshot:
    return EverkeepSnapshot(state="unavailable", detail=detail)


def _status_path() -> Path | None:
    raw = os.getenv("EVERKEEP_STATUS_FILE", "").strip()
    return Path(raw) if raw else None


def _validate(payload: Any) -> EverkeepSnapshot:
    if not isinstance(payload, dict):
        return _unavailable("Everkeep status is not a JSON object.")
    if payload.get("schema_version") != STATUS_SCHEMA_VERSION:
        return _unavailable("Everkeep status uses an unsupported contract version.")

    producer = payload.get("producer")
    if not isinstance(producer, dict):
        return _unavailable("Everkeep status is missing producer metadata.")
    runtime_authority = producer.get("runtime_authority")
    adapter_id = producer.get("adapter_id")
    if not isinstance(runtime_authority, str) or not runtime_authority.startswith("GoreeCloud/"):
        return _unavailable("Everkeep status has invalid runtime authority.")
    if not isinstance(adapter_id, str) or not adapter_id:
        return _unavailable("Everkeep status has invalid adapter identity.")

    generated_at = payload.get("generated_at")
    if not isinstance(generated_at, str) or not generated_at:
        return _unavailable("Everkeep status is missing its generation timestamp.")

    state = payload.get("state")
    if state not in ALLOWED_STATES:
        return _unavailable("Everkeep status has an unsupported state.")

    privacy = payload.get("privacy")
    if not isinstance(privacy, dict):
        return _unavailable("Everkeep status is missing sensitive-content guarantees.")
    required_guarantees = (
        "contains_backup_contents",
        "contains_file_inventory",
        "contains_recovery_secrets",
        "contains_credentials",
        "contains_private_paths",
        "contains_personal_records",
        "contains_raw_legacy_records",
    )
    for guarantee in required_guarantees:
        if privacy.get(guarantee) is not False:
            return _unavailable("Everkeep status was rejected because sensitive recovery content is present or undeclared.")

    acceptance = payload.get("acceptance")
    if not isinstance(acceptance, dict):
        return _unavailable("Everkeep status is missing acceptance metadata.")
    if acceptance.get("runtime_acceptance_required") is not True:
        return _unavailable("Everkeep status must preserve the runtime acceptance boundary.")
    production_approved = acceptance.get("production_approved")
    if not isinstance(production_approved, bool):
        return _unavailable("Everkeep status has invalid production approval state.")

    resilience = payload.get("resilience")
    if not isinstance(resilience, dict):
        return _unavailable("Everkeep status is missing resilience state.")

    normalized = {}
    for key in ("recovery_readiness", "backup_verification", "portability_continuity", "preservation"):
        value = resilience.get(key)
        if value not in ALLOWED_CAPABILITY_STATES:
            return _unavailable(f"Everkeep status has invalid {key.replace('_', ' ')} state.")
        normalized[key] = value

    capability_rows = payload.get("capabilities")
    if not isinstance(capability_rows, list):
        return _unavailable("Everkeep status capabilities are malformed.")
    capabilities: list[EverkeepCapability] = []
    seen: set[str] = set()
    for row in capability_rows:
        if not isinstance(row, dict):
            return _unavailable("Everkeep capability status is malformed.")
        capability_id = row.get("id")
        capability_state = row.get("state")
        if not isinstance(capability_id, str) or not capability_id or capability_id in seen:
            return _unavailable("Everkeep capability identity is missing or duplicated.")
        if capability_state not in ALLOWED_CAPABILITY_STATES:
            return _unavailable("Everkeep capability status is unsupported.")
        seen.add(capability_id)
        capabilities.append(EverkeepCapability(id=capability_id, state=capability_state))

    detail = (
        f"Everkeep status from {adapter_id}: recovery {normalized['recovery_readiness']}, "
        f"backup verification {normalized['backup_verification']}, "
        f"continuity {normalized['portability_continuity']}, preservation {normalized['preservation']}."
    )

    return EverkeepSnapshot(
        state=state,
        detail=detail,
        producer=runtime_authority,
        generated_at=generated_at,
        recovery_readiness=normalized["recovery_readiness"],
        backup_verification=normalized["backup_verification"],
        portability_continuity=normalized["portability_continuity"],
        preservation=normalized["preservation"],
        capabilities=tuple(capabilities),
        production_approved=production_approved,
    )


def everkeep_snapshot() -> EverkeepSnapshot:
    """Load one sanitized Everkeep status file without network access."""
    path = _status_path()
    if path is None:
        return _unavailable("Everkeep status is disabled until EVERKEEP_STATUS_FILE points to an approved sanitized status document.")
    if not path.is_file():
        return _unavailable("Configured Everkeep status file is unavailable.")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return _unavailable("Configured Everkeep status file could not be safely read.")
    return _validate(payload)
