"""Privacy-safe GoreeCloud Privacy Shield status integration.

Manager reads only the sanitized Privacy Shield status contract produced by an approved
runtime adapter. It never ingests browsing history, DNS queries, network flows, credentials,
device identifiers, or other raw private activity to render privacy status.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


STATUS_SCHEMA_VERSION = 1
ALLOWED_STATES = {"protected", "partial", "attention", "unavailable", "development"}
ALLOWED_CAPABILITY_STATES = {"active", "inactive", "pending-acceptance", "unavailable"}


@dataclass(frozen=True)
class PrivacyShieldCapability:
    id: str
    state: str


@dataclass(frozen=True)
class PrivacyShieldSnapshot:
    state: str
    detail: str
    product: str = "GoreeCloud Privacy Shield"
    producer: str = ""
    generated_at: str = ""
    capabilities: tuple[PrivacyShieldCapability, ...] = field(default_factory=tuple)
    production_approved: bool = False

    def integration_status(self) -> dict[str, str]:
        return {"state": self.state, "detail": self.detail}

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["capabilities"] = [asdict(capability) for capability in self.capabilities]
        return payload


def _unavailable(detail: str) -> PrivacyShieldSnapshot:
    return PrivacyShieldSnapshot(state="unavailable", detail=detail)


def _status_path() -> Path | None:
    raw = os.getenv("PRIVACY_SHIELD_STATUS_FILE", "").strip()
    return Path(raw) if raw else None


def _validate(payload: Any) -> PrivacyShieldSnapshot:
    if not isinstance(payload, dict):
        return _unavailable("Privacy Shield status is not a JSON object.")
    if payload.get("schema_version") != STATUS_SCHEMA_VERSION:
        return _unavailable("Privacy Shield status uses an unsupported contract version.")

    producer = payload.get("producer")
    if not isinstance(producer, dict):
        return _unavailable("Privacy Shield status is missing producer metadata.")
    adapter_id = producer.get("adapter_id")
    product = producer.get("product")
    authority = producer.get("runtime_authority")
    contract_version = producer.get("adapter_contract_version")
    if not isinstance(adapter_id, str) or not adapter_id:
        return _unavailable("Privacy Shield status has invalid adapter identity.")
    if not isinstance(product, str) or not product:
        return _unavailable("Privacy Shield status has invalid product identity.")
    if not isinstance(authority, str) or not authority.startswith("GoreeCloud/"):
        return _unavailable("Privacy Shield status has invalid runtime authority.")
    if not isinstance(contract_version, int) or contract_version < 1:
        return _unavailable("Privacy Shield status has invalid adapter contract version.")

    generated_at = payload.get("generated_at")
    if not isinstance(generated_at, str) or not generated_at:
        return _unavailable("Privacy Shield status is missing its generation timestamp.")

    state = payload.get("state")
    if state not in ALLOWED_STATES:
        return _unavailable("Privacy Shield status has an unsupported state.")

    privacy = payload.get("privacy")
    if not isinstance(privacy, dict):
        return _unavailable("Privacy Shield status is missing privacy guarantees.")
    if privacy.get("raw_private_activity_included") is not False:
        return _unavailable("Privacy Shield status was rejected because raw private activity is present or undeclared.")
    if privacy.get("contains_credentials") is not False:
        return _unavailable("Privacy Shield status was rejected because credential content is present or undeclared.")
    if privacy.get("contains_identifiers") is not False:
        return _unavailable("Privacy Shield status was rejected because identifying content is present or undeclared.")

    acceptance = payload.get("acceptance")
    if not isinstance(acceptance, dict):
        return _unavailable("Privacy Shield status is missing acceptance metadata.")
    if acceptance.get("runtime_acceptance_required") is not True:
        return _unavailable("Privacy Shield status must preserve the runtime acceptance boundary.")
    production_approved = acceptance.get("production_approved")
    if not isinstance(production_approved, bool):
        return _unavailable("Privacy Shield status has invalid production approval state.")

    capabilities_raw = payload.get("capabilities")
    if not isinstance(capabilities_raw, list) or not capabilities_raw:
        return _unavailable("Privacy Shield status must declare at least one capability.")

    capabilities: list[PrivacyShieldCapability] = []
    seen: set[str] = set()
    for item in capabilities_raw:
        if not isinstance(item, dict):
            return _unavailable("Privacy Shield capability status is malformed.")
        capability_id = item.get("id")
        capability_state = item.get("state")
        if not isinstance(capability_id, str) or not capability_id or capability_id in seen:
            return _unavailable("Privacy Shield capability identity is missing or duplicated.")
        if capability_state not in ALLOWED_CAPABILITY_STATES:
            return _unavailable("Privacy Shield capability status is unsupported.")
        seen.add(capability_id)
        capabilities.append(PrivacyShieldCapability(id=capability_id, state=capability_state))

    active_count = sum(capability.state == "active" for capability in capabilities)
    pending_count = sum(capability.state == "pending-acceptance" for capability in capabilities)
    if production_approved:
        detail = f"{product} reports {active_count} active Privacy Shield capabilities from {adapter_id}."
    else:
        detail = f"{product} reports {active_count} active and {pending_count} pending-acceptance Privacy Shield capabilities; production approval remains false."

    return PrivacyShieldSnapshot(
        state=state,
        detail=detail,
        product=product,
        producer=authority,
        generated_at=generated_at,
        capabilities=tuple(capabilities),
        production_approved=production_approved,
    )


def privacy_shield_snapshot() -> PrivacyShieldSnapshot:
    """Load one sanitized Privacy Shield status file without network access."""
    path = _status_path()
    if path is None:
        return _unavailable("Privacy Shield status is disabled until PRIVACY_SHIELD_STATUS_FILE points to an approved sanitized status document.")
    if not path.is_file():
        return _unavailable("Configured Privacy Shield status file is unavailable.")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return _unavailable("Configured Privacy Shield status file could not be safely read.")
    return _validate(payload)
