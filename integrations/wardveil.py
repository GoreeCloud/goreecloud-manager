"""Read-only Wardveil Security status visibility through GoreeCloud Mesh.

Manager consumes only minimized producer-authoritative ``security-status`` evidence
published by Wardveil Security to GoreeCloud Mesh. Mesh authenticates the read path and
preserves the producer envelope; it does not become the security authority. Manager
therefore presents Wardveil's producer outcome, scope, provenance, and freshness without
turning transport success into a security verdict or manufacturing a ``Protected by
Wardveil`` claim.

The evidence credential is deliberately separate from Manager's Platform Registry and
live-event credentials. It must carry only ``mesh.evidence.read`` for this consumer path.
"""

from __future__ import annotations

import os
import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx

EVIDENCE_PATH = "/v1/evidence/envelopes"
EVIDENCE_VERSION = "goreecloud.evidence-envelope.v1"
WARDVEIL_SYSTEM = "wardveil-security"
WARDVEIL_REPOSITORY = "GoreeCloud/goreecloud-wardveil-security"
WARDVEIL_STATUS_CONTRACT = "contracts/wardveil.status.schema.json"
WARDVEIL_AUTHORITY_DOMAIN = "security"
WARDVEIL_STATUS_ASSERTION = "security-status"
WARDVEIL_OUTCOMES = {"protected", "attention", "degraded", "unknown", "not_applicable"}
DATA_CLASSES = {"public", "operational", "derived"}
EXPECTED_RESPONSE_FIELDS = {"count", "current_count", "stale_count", "envelopes", "note"}
EXPECTED_ENVELOPE_FIELDS = {
    "version",
    "id",
    "producer",
    "authority_domain",
    "subject",
    "assertion",
    "outcome",
    "source",
    "observed_at",
    "valid_until",
    "data_class",
    "summary",
    "payload_digest",
    "contains_user_content",
    "contains_secret_material",
    "fresh",
}
EXPECTED_PRODUCER_FIELDS = {"system", "repository", "revision", "contract"}
EXPECTED_SUBJECT_FIELDS = {"kind", "id", "scope"}
REVISION_PATTERN = re.compile(r"^[0-9a-f]{40}$")
DIGEST_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")
MAX_CREDENTIAL_LENGTH = 16_384
MAX_RESPONSE_BYTES = 1 << 20
MAX_ENVELOPES = 128
MAX_ID_CHARS = 128
MAX_TEXT_CHARS = 256
MAX_SUMMARY_CHARS = 512
DEFAULT_TIMEOUT_SECONDS = 5.0
MAX_TIMEOUT_SECONDS = 30.0


@dataclass(frozen=True)
class WardveilEvidence:
    subject_kind: str
    subject_id: str
    subject_scope: str
    outcome: str
    observed_at: datetime
    valid_until: datetime
    fresh: bool
    producer_revision: str
    summary: str

    @property
    def freshness_label(self) -> str:
        return "current" if self.fresh else "stale"

    @property
    def outcome_label(self) -> str:
        return self.outcome.replace("_", " ").title()


@dataclass(frozen=True)
class WardveilSnapshot:
    state: str
    detail: str
    condition: str = "unknown"
    records: tuple[WardveilEvidence, ...] = ()
    current_count: int = 0
    stale_count: int = 0

    def integration_status(self) -> dict[str, str]:
        return {"state": self.state, "detail": self.detail}


class WardveilProtocolError(ValueError):
    """Raised when Mesh returns Wardveil evidence Manager cannot safely present."""


def _enabled() -> bool:
    return os.getenv("WARDVEIL_STATUS_ENABLED", "false").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _timeout_seconds() -> float:
    raw = os.getenv("WARDVEIL_STATUS_TIMEOUT_SECONDS", str(DEFAULT_TIMEOUT_SECONDS)).strip()
    try:
        value = float(raw)
    except ValueError:
        return DEFAULT_TIMEOUT_SECONDS
    if value <= 0:
        return DEFAULT_TIMEOUT_SECONDS
    return min(value, MAX_TIMEOUT_SECONDS)


def _validate_token(value: str) -> tuple[str | None, str | None]:
    token = value.strip()
    if not token:
        return None, "The configured Mesh Wardveil evidence token is empty."
    if len(token) > MAX_CREDENTIAL_LENGTH:
        return None, "The configured Mesh Wardveil evidence token exceeds the approved size bound."
    if "\r" in token or "\n" in token:
        return None, "The configured Mesh Wardveil evidence token contains invalid line breaks."
    return token, None


def _configured_token() -> tuple[str | None, str | None]:
    direct = os.getenv("MESH_WARDVEIL_EVIDENCE_TOKEN", "")
    file_path = os.getenv("MESH_WARDVEIL_EVIDENCE_TOKEN_FILE", "").strip()
    if direct.strip() and file_path:
        return None, "Set only one Mesh Wardveil evidence token source."
    if file_path:
        try:
            token = Path(file_path).read_text(encoding="utf-8")
        except OSError:
            return None, "The configured Mesh Wardveil evidence token file could not be read."
        return _validate_token(token)
    if direct.strip():
        return _validate_token(direct)
    return None, "Missing MESH_WARDVEIL_EVIDENCE_TOKEN or MESH_WARDVEIL_EVIDENCE_TOKEN_FILE."


def _api_url() -> tuple[str | None, str | None]:
    base_url = os.getenv("MESH_API_URL", "").strip().rstrip("/")
    if not base_url:
        return None, "Missing MESH_API_URL."
    parsed = urlparse(base_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None, "MESH_API_URL must be an absolute HTTP(S) URL."
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        return None, "MESH_API_URL must not embed credentials, query parameters, or fragments."
    loopback = parsed.hostname in {"127.0.0.1", "localhost", "::1"}
    if parsed.scheme != "https" and not (parsed.scheme == "http" and loopback):
        return None, "MESH_API_URL requires HTTPS except for loopback development."
    return f"{base_url}{EVIDENCE_PATH}", None


def _mapping(value: Any, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise WardveilProtocolError(f"Mesh returned an invalid {field} object.")
    return value


def _bounded_text(value: Any, field: str, maximum: int, *, required: bool = True) -> str:
    if value is None and not required:
        return ""
    if not isinstance(value, str):
        raise WardveilProtocolError(f"Mesh returned an invalid {field} value.")
    text = value.strip()
    if required and not text:
        raise WardveilProtocolError(f"Mesh returned a blank required {field} value.")
    if len(text) > maximum:
        raise WardveilProtocolError(f"Mesh returned an oversized {field} value.")
    if any(unicodedata.category(char).startswith("C") for char in text):
        raise WardveilProtocolError(f"Mesh returned control characters in {field}.")
    return text


def _timestamp(value: Any, field: str) -> datetime:
    text = _bounded_text(value, field, MAX_TEXT_CHARS)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise WardveilProtocolError(f"Mesh returned an invalid {field} timestamp.") from exc
    if parsed.tzinfo is None:
        raise WardveilProtocolError(f"Mesh returned {field} without a timezone.")
    return parsed.astimezone(timezone.utc)


def _closed_keys(value: dict[str, Any], expected: set[str], field: str) -> None:
    # Optional JSON-schema properties may be omitted; unknown properties are rejected.
    if not set(value).issubset(expected):
        raise WardveilProtocolError(f"Mesh returned an extended {field} shape.")


def _evidence(raw: Any, *, now: datetime) -> WardveilEvidence:
    value = _mapping(raw, "Wardveil evidence envelope")
    _closed_keys(value, EXPECTED_ENVELOPE_FIELDS, "Wardveil evidence envelope")
    required = {
        "version",
        "id",
        "producer",
        "authority_domain",
        "subject",
        "assertion",
        "outcome",
        "source",
        "observed_at",
        "valid_until",
        "data_class",
        "contains_user_content",
        "contains_secret_material",
        "fresh",
    }
    if not required.issubset(value):
        raise WardveilProtocolError("Mesh returned incomplete Wardveil evidence.")
    if value.get("version") != EVIDENCE_VERSION:
        raise WardveilProtocolError("Mesh returned an unsupported evidence-envelope version.")
    _bounded_text(value.get("id"), "evidence id", MAX_ID_CHARS)

    producer = _mapping(value.get("producer"), "Wardveil producer")
    if set(producer) != EXPECTED_PRODUCER_FIELDS:
        raise WardveilProtocolError("Mesh returned an invalid Wardveil producer identity.")
    if producer.get("system") != WARDVEIL_SYSTEM:
        raise WardveilProtocolError("Mesh returned security-status evidence from the wrong producer.")
    if producer.get("repository") != WARDVEIL_REPOSITORY:
        raise WardveilProtocolError("Mesh returned Wardveil evidence with the wrong repository authority.")
    revision = _bounded_text(producer.get("revision"), "producer revision", 40)
    if not REVISION_PATTERN.fullmatch(revision):
        raise WardveilProtocolError("Mesh returned Wardveil evidence without an exact producer revision.")
    if producer.get("contract") != WARDVEIL_STATUS_CONTRACT:
        raise WardveilProtocolError("Mesh returned security-status evidence against an unsupported Wardveil contract.")

    if value.get("authority_domain") != WARDVEIL_AUTHORITY_DOMAIN:
        raise WardveilProtocolError("Mesh returned Wardveil evidence outside the security authority domain.")
    if value.get("assertion") != WARDVEIL_STATUS_ASSERTION:
        raise WardveilProtocolError("Mesh returned an unexpected Wardveil assertion family.")
    outcome = _bounded_text(value.get("outcome"), "Wardveil outcome", MAX_TEXT_CHARS)
    if outcome not in WARDVEIL_OUTCOMES:
        raise WardveilProtocolError("Mesh returned an unsupported Wardveil security-status outcome.")

    subject = _mapping(value.get("subject"), "Wardveil evidence subject")
    _closed_keys(subject, EXPECTED_SUBJECT_FIELDS, "Wardveil evidence subject")
    if not {"kind", "id"}.issubset(subject):
        raise WardveilProtocolError("Mesh returned incomplete Wardveil subject identity.")
    subject_kind = _bounded_text(subject.get("kind"), "subject kind", MAX_ID_CHARS)
    subject_id = _bounded_text(subject.get("id"), "subject id", MAX_ID_CHARS)
    subject_scope = _bounded_text(
        subject.get("scope"),
        "subject scope",
        MAX_ID_CHARS,
        required=False,
    )

    _bounded_text(value.get("source"), "producer evidence reference", MAX_TEXT_CHARS)
    data_class = _bounded_text(value.get("data_class"), "evidence data class", MAX_TEXT_CHARS)
    if data_class not in DATA_CLASSES:
        raise WardveilProtocolError("Mesh returned an unsupported Wardveil evidence data class.")
    if value.get("contains_user_content") is not False or value.get("contains_secret_material") is not False:
        raise WardveilProtocolError("Mesh returned Wardveil evidence that is not approved for minimized status display.")

    summary = _bounded_text(
        value.get("summary"),
        "evidence summary",
        MAX_SUMMARY_CHARS,
        required=False,
    )
    digest = value.get("payload_digest")
    if digest is not None:
        digest_text = _bounded_text(digest, "payload digest", 71)
        if not DIGEST_PATTERN.fullmatch(digest_text):
            raise WardveilProtocolError("Mesh returned an invalid Wardveil payload digest.")

    observed_at = _timestamp(value.get("observed_at"), "observed_at")
    valid_until = _timestamp(value.get("valid_until"), "valid_until")
    if observed_at > now:
        raise WardveilProtocolError("Mesh returned Wardveil evidence observed in the future.")
    if valid_until <= observed_at:
        raise WardveilProtocolError("Mesh returned Wardveil evidence with an invalid validity window.")
    fresh = value.get("fresh")
    if not isinstance(fresh, bool):
        raise WardveilProtocolError("Mesh returned an invalid Wardveil freshness flag.")
    locally_current = valid_until > now
    if fresh != locally_current:
        raise WardveilProtocolError("Mesh freshness disagrees with the Wardveil evidence validity window.")

    return WardveilEvidence(
        subject_kind=subject_kind,
        subject_id=subject_id,
        subject_scope=subject_scope,
        outcome=outcome,
        observed_at=observed_at,
        valid_until=valid_until,
        fresh=fresh,
        producer_revision=revision,
        summary=summary,
    )


def _snapshot(payload: Any, *, now: datetime) -> WardveilSnapshot:
    value = _mapping(payload, "Mesh evidence response")
    if set(value) != EXPECTED_RESPONSE_FIELDS:
        raise WardveilProtocolError("Mesh returned an unsupported evidence response shape.")
    envelopes = value.get("envelopes")
    count = value.get("count")
    current_count = value.get("current_count")
    stale_count = value.get("stale_count")
    counts = (count, current_count, stale_count)
    if any(isinstance(item, bool) or not isinstance(item, int) or item < 0 for item in counts):
        raise WardveilProtocolError("Mesh returned invalid Wardveil evidence counts.")
    if not isinstance(envelopes, list) or count != len(envelopes):
        raise WardveilProtocolError("Mesh returned inconsistent Wardveil evidence counts.")
    if count > MAX_ENVELOPES:
        raise WardveilProtocolError("Mesh returned more Wardveil status records than Manager accepts.")
    if current_count + stale_count != count:
        raise WardveilProtocolError("Mesh returned inconsistent Wardveil freshness counts.")

    records = tuple(_evidence(item, now=now) for item in envelopes)
    if sum(item.fresh for item in records) != current_count:
        raise WardveilProtocolError("Mesh Wardveil current-count disagrees with envelope freshness.")
    if len({(item.subject_kind, item.subject_id, item.subject_scope, item.observed_at) for item in records}) != len(records):
        raise WardveilProtocolError("Mesh returned duplicate Wardveil status observations.")

    # Preserve only the latest producer observation for each subject/scope. History remains
    # in Mesh; Manager does not become another evidence store.
    latest: dict[tuple[str, str, str], WardveilEvidence] = {}
    for item in records:
        key = (item.subject_kind, item.subject_id, item.subject_scope)
        previous = latest.get(key)
        if previous is None or item.observed_at > previous.observed_at:
            latest[key] = item
    displayed = tuple(sorted(latest.values(), key=lambda item: (item.subject_kind, item.subject_id, item.subject_scope)))
    displayed_current = sum(item.fresh for item in displayed)
    displayed_stale = len(displayed) - displayed_current

    if not displayed:
        return WardveilSnapshot(
            state="unknown",
            detail=(
                "Mesh returned no Wardveil security-status evidence. Manager cannot infer a security state "
                "from an empty evidence transport."
            ),
            condition="empty",
        )
    if displayed_current == 0:
        return WardveilSnapshot(
            state="stale",
            detail=(
                "Only stale Wardveil security-status evidence is available. Historical producer outcomes "
                "remain visible but are not current security claims."
            ),
            condition="stale-only",
            records=displayed,
            current_count=0,
            stale_count=displayed_stale,
        )
    detail = (
        f"Verified minimized Wardveil security-status evidence is available for {len(displayed)} subject(s) "
        "through the authenticated Mesh evidence plane. Manager presents producer outcomes only."
    )
    if displayed_stale:
        detail += f" {displayed_stale} displayed subject(s) have stale latest evidence."
    return WardveilSnapshot(
        state="available" if not displayed_stale else "degraded",
        detail=detail,
        condition="current" if not displayed_stale else "mixed-freshness",
        records=displayed,
        current_count=displayed_current,
        stale_count=displayed_stale,
    )


def wardveil_snapshot() -> WardveilSnapshot:
    """Return a bounded read-only Wardveil status snapshot from Mesh evidence."""

    if not _enabled():
        return WardveilSnapshot(
            state="disabled",
            detail="Wardveil Security status visibility is disabled until explicitly configured.",
            condition="disabled",
        )

    api_url, url_error = _api_url()
    token, token_error = _configured_token()
    configuration_errors = [error for error in (url_error, token_error) if error]
    if configuration_errors:
        return WardveilSnapshot(
            state="misconfigured",
            detail=" ".join(configuration_errors),
            condition="misconfigured",
        )

    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {token}",
        "Cache-Control": "no-store",
        "User-Agent": "goreecloud-manager/0.1",
    }
    params = {
        "producer": WARDVEIL_SYSTEM,
        "authority_domain": WARDVEIL_AUTHORITY_DOMAIN,
        "assertion": WARDVEIL_STATUS_ASSERTION,
    }
    try:
        response = httpx.get(
            api_url,
            headers=headers,
            params=params,
            timeout=_timeout_seconds(),
        )
    except httpx.TimeoutException:
        return WardveilSnapshot(
            state="unavailable",
            detail="GoreeCloud Mesh did not return Wardveil status evidence before the configured timeout.",
            condition="unreachable",
        )
    except httpx.RequestError:
        return WardveilSnapshot(
            state="unavailable",
            detail="Manager could not reach the configured GoreeCloud Mesh evidence endpoint.",
            condition="unreachable",
        )

    if response.status_code == 401:
        return WardveilSnapshot(
            state="unavailable",
            detail="GoreeCloud Mesh rejected the configured Wardveil evidence-read credential.",
            condition="authentication-rejected",
        )
    if response.status_code == 403:
        return WardveilSnapshot(
            state="unavailable",
            detail="GoreeCloud Mesh denied the Wardveil evidence request; mesh.evidence.read is required.",
            condition="authorization-denied",
        )
    if response.status_code == 404:
        return WardveilSnapshot(
            state="unavailable",
            detail="The configured GoreeCloud Mesh evidence endpoint is not available.",
            condition="endpoint-unavailable",
        )
    try:
        response.raise_for_status()
    except httpx.HTTPStatusError:
        return WardveilSnapshot(
            state="unavailable",
            detail=f"GoreeCloud Mesh evidence API returned HTTP {response.status_code}.",
            condition="upstream-error",
        )

    if len(response.content) > MAX_RESPONSE_BYTES:
        return WardveilSnapshot(
            state="unavailable",
            detail="GoreeCloud Mesh returned Wardveil evidence larger than Manager's approved response bound.",
            condition="response-too-large",
        )
    try:
        return _snapshot(response.json(), now=_utc_now())
    except (ValueError, TypeError, WardveilProtocolError):
        return WardveilSnapshot(
            state="unavailable",
            detail="GoreeCloud Mesh returned Wardveil evidence Manager could not safely interpret.",
            condition="schema-invalid",
        )
