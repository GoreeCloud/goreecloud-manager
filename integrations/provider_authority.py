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


class ProviderEvidenceError(ValueError):
    pass


def _text(value: Any, field: str, *, limit: int = MAX_TEXT) -> str:
    if not isinstance(value, str) or not value:
        raise ProviderEvidenceError(f"{field} must be a non-empty string")
    if value != value.strip():
        raise ProviderEvidenceError(f"{field} must be canonical and must not contain surrounding whitespace")
    if len(value) > limit:
        raise ProviderEvidenceError(f"{field} exceeds Manager's display bound")
    if any(unicodedata.category(char).startswith("C") for char in value):
        raise ProviderEvidenceError(f"{field} contains control characters")
    return value


def _aware_datetime(value: Any, field: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ProviderEvidenceError(f"{field} must include timezone information")
    return value.astimezone(timezone.utc)


@dataclass(frozen=True)
class ProviderEvidenceView:
    provider_system: str
    authority_domain: str
    assertion: str
    producer_revision: str
    producer_outcome: str
    observed_at: datetime
    valid_until: datetime
    evaluated_at: datetime
    evidence_reference: str
    payload_digest: str
    state: str

    def __post_init__(self) -> None:
        authority_by_system = {
            PRIVACY_SHIELD.system: PRIVACY_SHIELD,
            EVERKEEP.system: EVERKEEP,
        }
        authority = authority_by_system.get(self.provider_system)
        if authority is None:
            raise ProviderEvidenceError("provider evidence view system is not governed")
        if self.authority_domain != authority.authority_domain:
            raise ProviderEvidenceError("provider evidence view authority domain mismatch")
        if self.assertion != authority.assertion:
            raise ProviderEvidenceError("provider evidence view assertion mismatch")

        revision = _text(self.producer_revision, "producer_revision", limit=40)
        if not REVISION.fullmatch(revision):
            raise ProviderEvidenceError("provider evidence view revision must be an exact commit SHA")
        _text(self.producer_outcome, "producer_outcome")
        _text(self.evidence_reference, "evidence_reference", limit=1000)
        digest = _text(self.payload_digest, "payload_digest", limit=71)
        if not DIGEST.fullmatch(digest):
            raise ProviderEvidenceError("provider evidence view payload digest is invalid")

        observed = _aware_datetime(self.observed_at, "provider evidence view observed_at")
        valid_until = _aware_datetime(self.valid_until, "provider evidence view valid_until")
        evaluated = _aware_datetime(self.evaluated_at, "provider evidence view evaluated_at")
        if valid_until <= observed:
            raise ProviderEvidenceError("provider evidence view validity window is invalid")
        if observed > evaluated:
            raise ProviderEvidenceError("provider evidence view cannot be observed in the future")
        expected_state = "current" if valid_until > evaluated else "stale"
        if self.state != expected_state:
            raise ProviderEvidenceError(
                "provider evidence view state does not match its evaluation time and validity window"
            )

    @property
    def current(self) -> bool:
        return self.state == "current"


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


def _iso_utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


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
        evaluated_at=current_time,
        evidence_reference=reference,
        payload_digest=digest,
        state="current" if valid_until > current_time else "stale",
    )


def integration_status(view: ProviderEvidenceView) -> dict[str, str]:
    """Return Manager-authored display state without adopting producer wording.

    The opaque provider outcome remains available on ``ProviderEvidenceView`` for
    a provider-owned field or dedicated UI surface. Manager-authored explanatory
    text deliberately does not interpolate that untrusted wording, which keeps
    producer claims visually and semantically separate from Manager's own state.
    """
    if view.current:
        return {
            "state": "available",
            "detail": (
                f"Current {view.provider_system} producer evidence is available. "
                "Manager is displaying provider evidence only and does not reinterpret "
                "the provider-owned outcome."
            ),
        }
    return {
        "state": "attention",
        "detail": (
            f"Only stale {view.provider_system} producer evidence is available. "
            "Manager does not infer a current privacy or recovery state from stale evidence."
        ),
    }


def provider_status_record(view: ProviderEvidenceView) -> dict[str, Any]:
    """Return a structured, non-authorizing record for Manager UI/API consumers.

    The producer-owned outcome is carried as its own field instead of being
    interpolated into Manager-authored prose. The explicit false authority flags
    make this record unsuitable for accidental use as a privacy/recovery decision.
    """
    display = integration_status(view)
    return {
        "provider_system": view.provider_system,
        "authority_domain": view.authority_domain,
        "assertion": view.assertion,
        "producer_revision": view.producer_revision,
        "provider_outcome": view.producer_outcome,
        "observed_at": _iso_utc(view.observed_at),
        "valid_until": _iso_utc(view.valid_until),
        "evaluated_at": _iso_utc(view.evaluated_at),
        "evidence_reference": view.evidence_reference,
        "payload_digest": view.payload_digest,
        "manager_display_state": display["state"],
        "manager_detail": display["detail"],
        "manager_authority": False,
        "authority_transfer": False,
    }
