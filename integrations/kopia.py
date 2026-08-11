"""Read-only Kopia status-artifact integration for GoreeCloud Manager.

Kopia remains authoritative for repository and snapshot operations. Manager reads only a
sanitized JSON artifact produced by a delegated host-side collector. The Manager process
never executes Kopia, receives repository credentials, or receives Docker authority.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DEFAULT_STATUS_PATH = "/app/integrations/kopia/status.json"
DEFAULT_ARTIFACT_MAX_AGE_SECONDS = 8 * 60 * 60
DEFAULT_SNAPSHOT_MAX_AGE_SECONDS = 12 * 60 * 60
MAX_AGE_SECONDS = 7 * 24 * 60 * 60
SUPPORTED_SCHEMA_VERSION = 1

ATTEMPT_STATES = {"success", "skipped", "failed", "unknown"}
REPOSITORY_STATES = {"ok", "not_attempted", "unavailable", "error"}


def _enabled() -> bool:
    return os.getenv("KOPIA_ENABLED", "false").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _bounded_seconds(name: str, default: int) -> int:
    raw = os.getenv(name, str(default)).strip()
    try:
        value = int(raw)
    except ValueError:
        return default
    if value < 60:
        return 60
    return min(value, MAX_AGE_SECONDS)


def _parse_timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None

    normalized = value.strip()
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"

    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None

    if parsed.tzinfo is None:
        return None

    return parsed.astimezone(UTC)


def _nonnegative_int(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return None
    return value


def _age_seconds(value: datetime | None, *, now: datetime) -> int | None:
    if value is None:
        return None
    return max(0, int((now - value).total_seconds()))


def _duration_label(seconds: int | None) -> str:
    if seconds is None:
        return "Unknown"
    if seconds < 60:
        return f"{seconds} second" + ("" if seconds == 1 else "s")
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes} minute" + ("" if minutes == 1 else "s")
    hours = minutes // 60
    if hours < 48:
        return f"{hours} hour" + ("" if hours == 1 else "s")
    days = hours // 24
    return f"{days} day" + ("" if days == 1 else "s")


def _size_label(size_bytes: int | None) -> str:
    if size_bytes is None:
        return "Unknown"

    value = float(size_bytes)
    units = ("B", "KiB", "MiB", "GiB", "TiB")
    for unit in units:
        if value < 1024 or unit == units[-1]:
            if unit == "B":
                return f"{int(value)} {unit}"
            return f"{value:.1f} {unit}"
        value /= 1024

    return f"{size_bytes} B"


@dataclass(frozen=True)
class KopiaAttempt:
    state: str
    at: datetime | None
    reason: str

    @property
    def state_label(self) -> str:
        return {
            "success": "Successful",
            "skipped": "Skipped",
            "failed": "Failed",
            "unknown": "Unknown",
        }.get(self.state, "Unknown")

    @property
    def reason_label(self) -> str:
        return {
            "snapshot-created": "Snapshot created",
            "snapshot-observed": "Snapshot observed",
            "target-unavailable": "Backup target unavailable",
            "snapshot-failed": "Snapshot creation failed",
            "concurrent-run": "Another backup run was already active",
            "bootstrap": "Initial status bootstrap",
        }.get(
            self.reason,
            self.reason.replace("-", " ").strip().capitalize() or "Not reported",
        )


@dataclass(frozen=True)
class KopiaSnapshot:
    snapshot_id: str
    start_time: datetime | None
    end_time: datetime | None
    description: str
    size_bytes: int | None
    file_count: int | None
    directory_count: int | None
    error_count: int | None
    retention_reasons: tuple[str, ...]

    @property
    def size_label(self) -> str:
        return _size_label(self.size_bytes)


@dataclass(frozen=True)
class KopiaStatus:
    state: str
    detail: str
    generated_at: datetime | None = None
    artifact_age_seconds: int | None = None
    source_host: str = ""
    source_label: str = ""
    repository_state: str = ""
    repository_checked_at: datetime | None = None
    latest_attempt: KopiaAttempt | None = None
    latest_snapshot: KopiaSnapshot | None = None
    snapshot_age_seconds: int | None = None

    @property
    def artifact_age_label(self) -> str:
        return _duration_label(self.artifact_age_seconds)

    @property
    def snapshot_age_label(self) -> str:
        return _duration_label(self.snapshot_age_seconds)

    @property
    def repository_state_label(self) -> str:
        return {
            "ok": "Verified",
            "not_attempted": "Not queried on this attempt",
            "unavailable": "Unavailable",
            "error": "Query failed",
        }.get(self.repository_state, "Unknown")

    def integration_status(self) -> dict[str, str]:
        return {"state": self.state, "detail": self.detail}


def _unavailable(detail: str) -> KopiaStatus:
    return KopiaStatus(state="unavailable", detail=detail)


def _parse_attempt(value: Any) -> KopiaAttempt | None:
    if not isinstance(value, dict):
        return None

    state = value.get("state")
    reason = value.get("reason")
    at = _parse_timestamp(value.get("at"))
    if (
        state not in ATTEMPT_STATES
        or not isinstance(reason, str)
        or not reason.strip()
        or at is None
    ):
        return None

    return KopiaAttempt(
        state=state,
        at=at,
        reason=reason.strip(),
    )


def _parse_snapshot(value: Any) -> KopiaSnapshot | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        return None

    snapshot_id = value.get("id")
    if not isinstance(snapshot_id, str) or not snapshot_id.strip():
        return None

    start_time = _parse_timestamp(value.get("start_time"))
    end_time = _parse_timestamp(value.get("end_time"))
    if start_time is None or end_time is None or end_time < start_time:
        return None

    description = value.get("description", "")
    if not isinstance(description, str):
        description = ""

    retention = value.get("retention_reasons", [])
    if not isinstance(retention, list) or any(not isinstance(item, str) for item in retention):
        return None

    return KopiaSnapshot(
        snapshot_id=snapshot_id.strip(),
        start_time=start_time,
        end_time=end_time,
        description=description.strip(),
        size_bytes=_nonnegative_int(value.get("size_bytes")),
        file_count=_nonnegative_int(value.get("file_count")),
        directory_count=_nonnegative_int(value.get("directory_count")),
        error_count=_nonnegative_int(value.get("error_count")),
        retention_reasons=tuple(item.strip() for item in retention if item.strip()),
    )


def kopia_status(*, now: datetime | None = None) -> KopiaStatus:
    """Read and normalize the delegated Kopia status artifact."""

    if not _enabled():
        return KopiaStatus(
            state="disabled",
            detail="Native Kopia status visibility is disabled.",
        )

    status_path = os.getenv("KOPIA_STATUS_PATH", DEFAULT_STATUS_PATH).strip()
    if not status_path:
        return KopiaStatus(
            state="misconfigured",
            detail="Kopia status artifact path is not configured.",
        )

    try:
        raw = Path(status_path).read_text(encoding="utf-8")
    except FileNotFoundError:
        return _unavailable("Kopia status artifact is not available.")
    except OSError:
        return _unavailable("Manager could not read the Kopia status artifact.")

    try:
        payload = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return _unavailable("Kopia status artifact is malformed.")

    if not isinstance(payload, dict):
        return _unavailable("Kopia status artifact has an unexpected structure.")

    if payload.get("schema_version") != SUPPORTED_SCHEMA_VERSION:
        return _unavailable("Kopia status artifact schema is not supported.")

    generated_at = _parse_timestamp(payload.get("generated_at"))
    if generated_at is None:
        return _unavailable("Kopia status artifact has an invalid generation timestamp.")

    source = payload.get("source")
    repository_query = payload.get("repository_query")
    if not isinstance(source, dict) or not isinstance(repository_query, dict):
        return _unavailable("Kopia status artifact is missing required status fields.")

    source_host = source.get("host", "")
    source_label = source.get("label", "")
    if not isinstance(source_host, str) or not isinstance(source_label, str):
        return _unavailable("Kopia status artifact source fields are malformed.")

    repository_state = repository_query.get("state")
    if repository_state not in REPOSITORY_STATES:
        return _unavailable("Kopia status artifact repository state is invalid.")

    repository_checked_at = _parse_timestamp(repository_query.get("checked_at"))
    if repository_state != "not_attempted" and repository_checked_at is None:
        return _unavailable("Kopia status artifact repository timestamp is invalid.")

    latest_attempt = _parse_attempt(payload.get("latest_attempt"))
    if latest_attempt is None:
        return _unavailable("Kopia status artifact latest-attempt data is malformed.")

    latest_snapshot = _parse_snapshot(payload.get("latest_snapshot"))
    if payload.get("latest_snapshot") is not None and latest_snapshot is None:
        return _unavailable("Kopia status artifact snapshot data is malformed.")

    current = (now or datetime.now(UTC)).astimezone(UTC)
    artifact_age = _age_seconds(generated_at, now=current)
    snapshot_age = _age_seconds(
        latest_snapshot.end_time if latest_snapshot else None,
        now=current,
    )

    artifact_max_age = _bounded_seconds(
        "KOPIA_STATUS_MAX_AGE_SECONDS",
        DEFAULT_ARTIFACT_MAX_AGE_SECONDS,
    )
    snapshot_max_age = _bounded_seconds(
        "KOPIA_SNAPSHOT_MAX_AGE_SECONDS",
        DEFAULT_SNAPSHOT_MAX_AGE_SECONDS,
    )

    concerns: list[str] = []
    if generated_at > current:
        concerns.append("status artifact timestamp is in the future")
    elif artifact_age is not None and artifact_age > artifact_max_age:
        concerns.append("status artifact is stale")

    if latest_attempt.state == "skipped":
        concerns.append("latest scheduled backup attempt was skipped")
    elif latest_attempt.state == "failed":
        concerns.append("latest backup attempt failed")
    elif latest_attempt.state == "unknown":
        concerns.append("latest backup attempt is not yet known")

    if repository_state in {"unavailable", "error"}:
        concerns.append("latest repository query did not succeed")
    elif latest_attempt.state == "success" and repository_state != "ok":
        concerns.append("latest successful attempt was not verified by a repository query")

    if latest_snapshot is None:
        concerns.append("no latest snapshot is recorded")
    else:
        if latest_snapshot.end_time and latest_snapshot.end_time > current:
            concerns.append("latest snapshot timestamp is in the future")
        if latest_snapshot.error_count not in {None, 0}:
            concerns.append("latest snapshot reports errors")
        if snapshot_age is not None and snapshot_age > snapshot_max_age:
            concerns.append("latest snapshot is older than the configured freshness window")

    state = "degraded" if concerns else "healthy"
    if concerns:
        detail = "Native Kopia status verified; " + "; ".join(concerns) + "."
    else:
        detail = "Native Kopia status verified from the delegated read-only artifact."

    return KopiaStatus(
        state=state,
        detail=detail,
        generated_at=generated_at,
        artifact_age_seconds=artifact_age,
        source_host=source_host.strip(),
        source_label=source_label.strip(),
        repository_state=repository_state,
        repository_checked_at=repository_checked_at,
        latest_attempt=latest_attempt,
        latest_snapshot=latest_snapshot,
        snapshot_age_seconds=snapshot_age,
    )
