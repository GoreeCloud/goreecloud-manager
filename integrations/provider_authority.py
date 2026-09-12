"""Read-only normalized provider-authority evidence for GoreeCloud Manager.

Manager may present accepted producer evidence but never becomes Privacy Shield or
Everkeep authority. This module validates provenance, exact revisions, freshness,
and minimization before returning a bounded display record. It performs no network
request and grants no platform authority.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping

REVISION = re.compile(r"^[0-9a-f]{40}$")
DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
MAX_TEXT = 256


@dataclass(frozen=True)
class ProviderAuthority:
    system: str
    repository: str
    authority_domain: str
    assertion: str


PRIVACY_SHIELD = ProviderAuthority(
    system="privacy-shield",
    repository="GoreeCloud/goreecloud-privacy-shield",
    authority_domain="privacy",
    assertion="privacy-status",
)

EVERKEEP = ProviderAuthority(
    system="everkeep",
    repository="GoreeCloud/goreecloud-everkeep",
    authority_domain="recovery",
    assertion="recovery-readiness",
)


@dataclass(frozen=True)
class ProviderEvidenceView:
    provider_system: str
    authority_domain: str
    assertion: str
    producer_revision: str
    producer_outcome: str
    observed_at: datetime
    valid_until: datetime
    evidence_reference: str
    payload_digest: str
    state: str

    @property
    def current(self) -> bool:
        return self.state == "current"


class ProviderEvidenceError(ValueError):
    pass


def _text(value: Any, field: str, *, limit: int = MAX_TEXT) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ProviderEvidenceError(f"{field} must be a non-empty string")
    text = value.strip()
    if len(text) > limit:
        raise ProviderEvidenceError(f"{field} exceeds Manager's display bound")
    if any(unicodedata.category(char).startswith("C") for char in text):
        raise ProviderEvidenceError(f"{field} contains control characters")
    return text


def _time(value: Any, field: str) -> datetime:
    text = _text(value, field)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ProviderEvidenceError(f"{field} is not a valid timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ProviderEvidenceError(f"{field} must include timezone information")
    return parsed.astimezone(timezone.utc)


def _evaluation_time(now: datetime | None) -> datetime:
    if now is None:
        return datetime.now(timezone.utc)
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise ProviderEvidenceError("evaluation time must include timezone information")
    return now.astimezone(timezone.utc)


def normalize_provider_evidence(
    raw: Mapping[str, Any],
    *,
    authority: ProviderAuthority,
    now: datetime | None = None,
) -> ProviderEvidenceView:
    """Validate one producer record without interpreting the producer's outcome.

    The provider-specific outcome remains opaque. Manager derives only whether the
    record is current or stale for display; it never upgrades, combines, or converts
    producer state into Manager-owned privacy/recovery truth.
    """
    if not isinstance(raw, Mapping):
        raise ProviderEvidenceError("provider evidence must be an object")
    expected = {
        "producer",
        "authority_domain",
        "assertion",
        "outcome",
        "observed_at",
        "valid_until",
        "evidence_reference",
        "payload_digest",
        "contains_user_content",
        "contains_secret_material",
        "authority_transfer",
    }
    if set(raw) != expected:
        raise ProviderEvidenceError("provider evidence shape is not closed")

    producer = raw.get("producer")
    if not isinstance(producer, Mapping) or set(producer) != {"system", "repository", "revision"}:
        raise ProviderEvidenceError("producer identity is invalid")
    if producer.get("system") != authority.system:
        raise ProviderEvidenceError("producer system does not match configured authority")
    if producer.get("repository") != authority.repository:
        raise ProviderEvidenceError("producer repository does not match configured authority")
    revision = _text(producer.get("revision"), "producer.revision", limit=40)
    if not REVISION.fullmatch(revision):
        raise ProviderEvidenceError("producer revision must be an exact commit SHA")

    if raw.get("authority_domain") != authority.authority_domain:
        raise ProviderEvidenceError("provider authority domain mismatch")
    if raw.get("assertion") != authority.assertion:
        raise ProviderEvidenceError("provider assertion family mismatch")
    if raw.get("authority_transfer") is not False:
        raise ProviderEvidenceError("Manager must reject authority transfer")
    if raw.get("contains_user_content") is not False or raw.get("contains_secret_material") is not False:
        raise ProviderEvidenceError("provider evidence is not minimized for Manager display")

    outcome = _text(raw.get("outcome"), "outcome")
    reference = _text(raw.get("evidence_reference"), "evidence_reference", limit=1000)
    digest = _text(raw.get("payload_digest"), "payload_digest", limit=71)
    if not DIGEST.fullmatch(digest):
        raise ProviderEvidenceError("payload_digest must be an exact SHA-256 digest")

    observed = _time(raw.get("observed_at"), "observed_at")
    valid_until = _time(raw.get("valid_until"), "valid_until")
    current_time = _evaluation_time(now)
    if observed > current_time:
        raise ProviderEvidenceError("provider evidence cannot be observed in the future")
    if valid_until <= observed:
        raise ProviderEvidenceError("provider evidence validity window is invalid")

    return ProviderEvidenceView(
        provider_system=authority.system,
        authority_domain=authority.authority_domain,
        assertion=authority.assertion,
        producer_revision=revision,
        producer_outcome=outcome,
        observed_at=observed,
        valid_until=valid_until,
        evidence_reference=reference,
        payload_digest=digest,
        state="current" if valid_until > current_time else "stale",
    )


def integration_status(view: ProviderEvidenceView) -> dict[str, str]:
    """Return a bounded display state without interpreting provider outcome."""
    if view.current:
        detail = (
            f"Current {view.provider_system} producer evidence is available. "
            f"Producer outcome: {view.producer_outcome}. Manager is displaying provider evidence only."
        )
        return {"state": "available", "detail": detail}
    return {
        "state": "attention",
        "detail": (
            f"Only stale {view.provider_system} producer evidence is available. "
            "Manager does not infer a current privacy or recovery state from stale evidence."
        ),
    }
