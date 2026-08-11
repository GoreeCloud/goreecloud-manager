"""Read-only Healthchecks Management API adapter for GoreeCloud Manager.

The adapter uses only the documented checks-list endpoint and is designed for a
project-specific read-only API key. It never returns the configured key or raw
upstream response bodies to callers.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import httpx

DEFAULT_TIMEOUT_SECONDS = 5.0
MAX_TIMEOUT_SECONDS = 30.0
VALID_CHECK_STATES = {"new", "up", "grace", "down", "paused"}


@dataclass(frozen=True)
class Healthcheck:
    """Normalized Healthchecks fields approved for Manager display."""

    key: str
    name: str
    slug: str
    tags: tuple[str, ...]
    status: str
    started: bool
    last_ping: datetime | None
    next_ping: datetime | None
    timeout: int | None
    grace: int
    schedule: str
    timezone: str

    @property
    def attention(self) -> bool:
        return self.status in {"down", "grace"}

    @property
    def schedule_label(self) -> str:
        if self.schedule:
            return f"{self.schedule} ({self.timezone or 'UTC'})"
        if self.timeout:
            return _duration_label(self.timeout)
        return "Not reported"

    @property
    def grace_label(self) -> str:
        return _duration_label(self.grace) if self.grace else "None"


@dataclass(frozen=True)
class HealthchecksSnapshot:
    """A fail-soft snapshot of current Healthchecks monitoring state."""

    state: str
    detail: str
    checks: tuple[Healthcheck, ...] = ()

    @property
    def total(self) -> int:
        return len(self.checks)

    def count(self, status: str) -> int:
        return sum(1 for check in self.checks if check.status == status)

    @property
    def up(self) -> int:
        return self.count("up")

    @property
    def grace(self) -> int:
        return self.count("grace")

    @property
    def down(self) -> int:
        return self.count("down")

    @property
    def paused(self) -> int:
        return self.count("paused")

    @property
    def new(self) -> int:
        return self.count("new")

    @property
    def attention(self) -> int:
        return self.down + self.grace

    @property
    def kopia_check(self) -> Healthcheck | None:
        for check in self.checks:
            if (
                check.slug == "goreecloud-kopia-backup"
                or check.name.casefold() == "goreecloud kopia backup"
            ):
                return check
        return None

    def integration_status(self) -> dict[str, str]:
        """Return normalized registry state without private credentials."""
        return {"state": self.state, "detail": self.detail}


class HealthchecksProtocolError(ValueError):
    """Raised when Healthchecks returns an unexpected response shape."""


def _enabled() -> bool:
    return os.getenv("HEALTHCHECKS_ENABLED", "false").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _timeout_seconds() -> float:
    raw = os.getenv(
        "HEALTHCHECKS_TIMEOUT_SECONDS", str(DEFAULT_TIMEOUT_SECONDS)
    ).strip()
    try:
        value = float(raw)
    except ValueError:
        return DEFAULT_TIMEOUT_SECONDS
    if value <= 0:
        return DEFAULT_TIMEOUT_SECONDS
    return min(value, MAX_TIMEOUT_SECONDS)


def _parse_timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    normalized = value.strip().replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None


def _safe_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return max(parsed, 0)


def _duration_label(seconds: int) -> str:
    if seconds % 86400 == 0:
        days = seconds // 86400
        return f"{days} day" + ("" if days == 1 else "s")
    if seconds % 3600 == 0:
        hours = seconds // 3600
        return f"{hours} hour" + ("" if hours == 1 else "s")
    if seconds % 60 == 0:
        minutes = seconds // 60
        return f"{minutes} minute" + ("" if minutes == 1 else "s")
    return f"{seconds} seconds"


def _normalize_check(raw: Any) -> Healthcheck:
    if not isinstance(raw, dict):
        raise HealthchecksProtocolError(
            "Healthchecks returned a check entry that was not an object."
        )

    status = str(raw.get("status") or "").strip().lower()
    if status not in VALID_CHECK_STATES:
        raise HealthchecksProtocolError(
            "Healthchecks returned an unsupported check state."
        )

    tags_raw = raw.get("tags")
    tags = tuple(item for item in str(tags_raw or "").split() if item)
    grace = _safe_int(raw.get("grace"))
    timeout = _safe_int(raw.get("timeout"))

    return Healthcheck(
        key=str(raw.get("unique_key") or raw.get("uuid") or raw.get("slug") or ""),
        name=str(raw.get("name") or raw.get("slug") or "Unnamed check"),
        slug=str(raw.get("slug") or ""),
        tags=tags,
        status=status,
        started=bool(raw.get("started", False)),
        last_ping=_parse_timestamp(raw.get("last_ping")),
        next_ping=_parse_timestamp(raw.get("next_ping")),
        timeout=timeout,
        grace=grace or 0,
        schedule=str(raw.get("schedule") or ""),
        timezone=str(raw.get("tz") or ""),
    )


def _healthy_snapshot(payload: Any) -> HealthchecksSnapshot:
    if not isinstance(payload, dict) or not isinstance(payload.get("checks"), list):
        raise HealthchecksProtocolError(
            "Healthchecks returned an unexpected checks response."
        )

    rank = {"down": 0, "grace": 1, "new": 2, "paused": 3, "up": 4}
    checks = tuple(
        sorted(
            (_normalize_check(item) for item in payload["checks"]),
            key=lambda check: (rank[check.status], check.name.casefold()),
        )
    )

    if not checks:
        return HealthchecksSnapshot(
            state="degraded",
            detail="Healthchecks returned no checks for the configured project.",
            checks=checks,
        )

    attention = sum(1 for check in checks if check.attention)
    if attention:
        return HealthchecksSnapshot(
            state="degraded",
            detail=(
                f"Live read-only API data verified for {len(checks)} check(s); "
                f"{attention} require attention."
            ),
            checks=checks,
        )

    return HealthchecksSnapshot(
        state="healthy",
        detail=f"Live read-only API data verified for {len(checks)} check(s).",
        checks=checks,
    )


def healthchecks_snapshot() -> HealthchecksSnapshot:
    """Query Healthchecks and return a normalized, non-secret monitoring snapshot."""

    if not _enabled():
        return HealthchecksSnapshot(
            state="disabled",
            detail=(
                "Disabled until the read-only Healthchecks integration is "
                "explicitly enabled."
            ),
        )

    api_url = os.getenv("HEALTHCHECKS_API_URL", "").strip().rstrip("/")
    api_key = os.getenv("HEALTHCHECKS_API_KEY", "").strip()

    missing = []
    if not api_url:
        missing.append("HEALTHCHECKS_API_URL")
    if not api_key:
        missing.append("HEALTHCHECKS_API_KEY")
    if missing:
        return HealthchecksSnapshot(
            state="misconfigured",
            detail=(
                "Missing required Healthchecks configuration: "
                + ", ".join(missing)
                + "."
            ),
        )

    try:
        response = httpx.get(
            f"{api_url}/checks/",
            headers={
                "Accept": "application/json",
                "X-Api-Key": api_key,
                "User-Agent": "goreecloud-manager/0.1",
            },
            timeout=_timeout_seconds(),
        )
    except httpx.TimeoutException:
        return HealthchecksSnapshot(
            state="unavailable",
            detail="Healthchecks did not respond before the configured timeout.",
        )
    except httpx.RequestError:
        return HealthchecksSnapshot(
            state="unavailable",
            detail="Manager could not reach the configured Healthchecks API endpoint.",
        )

    if response.status_code == 401:
        return HealthchecksSnapshot(
            state="unavailable",
            detail="Healthchecks rejected the configured read-only API credential.",
        )

    if response.status_code == 403:
        return HealthchecksSnapshot(
            state="unavailable",
            detail="Healthchecks denied the configured API request path.",
        )

    try:
        response.raise_for_status()
    except httpx.HTTPStatusError:
        return HealthchecksSnapshot(
            state="unavailable",
            detail=f"Healthchecks API returned HTTP {response.status_code}.",
        )

    try:
        payload = response.json()
        return _healthy_snapshot(payload)
    except (ValueError, HealthchecksProtocolError):
        return HealthchecksSnapshot(
            state="unavailable",
            detail="Healthchecks returned a response Manager could not safely interpret.",
        )
