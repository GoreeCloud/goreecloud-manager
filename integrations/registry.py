"""Integration registry for GoreeCloud Manager.

The registry reports normalized application-facing state. Live adapters remain responsible
for querying their authoritative systems and returning only approved non-secret fields.
Manager never strengthens a producer claim: configuration, connectivity, availability,
privacy, security, and continuity remain distinct semantic families.
"""

from __future__ import annotations

import os
import re
from dataclasses import asdict, dataclass
from typing import Any


_PRESENTATION_STATES = frozenset(
    {
        "active",
        "available",
        "configured",
        "degraded",
        "disabled",
        "healthy",
        "inactive",
        "managed",
        "misconfigured",
        "paused",
        "planned",
        "ready",
        "restricted",
        "unavailable",
        "unknown",
    }
)
_SERVICE_AVAILABILITY_STATES = frozenset(
    {"unknown", "inactive", "available", "degraded", "unavailable"}
)
_REASON_TOKEN = re.compile(r"^[a-z0-9][a-z0-9_.-]{0,127}$")


@dataclass(frozen=True)
class IntegrationStatus:
    key: str
    name: str
    category: str
    state: str
    detail: str


def _enabled(name: str) -> bool:
    return os.getenv(name, "false").strip().lower() in {"1", "true", "yes", "on"}


def _normalized_detail(value: Any, fallback: str) -> str:
    if not isinstance(value, str):
        return fallback
    value = value.strip()
    return value if value else fallback


def _normalize_live_status(payload: dict[str, Any]) -> tuple[str, str]:
    """Normalize a legacy/live adapter state without inventing semantics."""

    raw_state = payload.get("state")
    state = raw_state.strip().lower() if isinstance(raw_state, str) else "unknown"
    if state not in _PRESENTATION_STATES:
        return (
            "unknown",
            "Adapter returned no recognized semantic state; Manager is presenting unknown.",
        )
    return state, _normalized_detail(
        payload.get("detail"),
        "The authoritative adapter did not provide additional state detail.",
    )


def _producer_availability_status(payload: dict[str, Any]) -> tuple[str, str]:
    """Consume only a producer-owned service-availability claim.

    Candidate Gateway, Beacon, and Conduit producers may expose other facts such as
    configuration validity, migration stage, authority, or connectivity. Those fields are
    deliberately ignored here because they are not service-availability evidence.
    """

    raw_state = payload.get("availability")
    state = raw_state.strip().lower() if isinstance(raw_state, str) else "unknown"
    if state not in _SERVICE_AVAILABILITY_STATES:
        return (
            "unknown",
            "Producer supplied no recognized service-availability state; Manager is presenting unknown.",
        )

    raw_reason = payload.get("availability_reason")
    reason = raw_reason.strip().lower() if isinstance(raw_reason, str) else ""
    if not _REASON_TOKEN.fullmatch(reason):
        reason = "reason_not_supplied"
    return state, f"Producer-owned service availability: {state}. Evidence reason: {reason}."


def integration_statuses(
    *,
    netbird_status: dict[str, Any] | None = None,
    healthchecks_status: dict[str, Any] | None = None,
    uptime_kuma_status: dict[str, Any] | None = None,
    beszel_status: dict[str, Any] | None = None,
    kopia_status: dict[str, Any] | None = None,
    tasks_status: dict[str, Any] | None = None,
    privacy_shield_status: dict[str, Any] | None = None,
    everkeep_status: dict[str, Any] | None = None,
    gateway_status: dict[str, Any] | None = None,
    beacon_status: dict[str, Any] | None = None,
    conduit_status: dict[str, Any] | None = None,
) -> list[dict[str, str]]:
    definitions = [
        ("privacy-shield", "Privacy Shield", "Privacy", None),
        ("everkeep", "Everkeep", "Protection / Continuity", "EVERKEEP_ENABLED"),
        ("netbird", "NetBird", "Network", "NETBIRD_ENABLED"),
        ("healthchecks", "Healthchecks", "Monitoring", "HEALTHCHECKS_ENABLED"),
        ("docker", "Docker", "Infrastructure", None),
        ("uptime-kuma", "Uptime Kuma", "Monitoring", "UPTIME_KUMA_ENABLED"),
        ("beszel", "Beszel", "Monitoring", "BESZEL_ENABLED"),
        ("kopia", "Kopia", "Protection", "KOPIA_ENABLED"),
        ("tasks", "GoreeCloud Tasks", "Work Management", "TASKS_ENABLED"),
        ("ntfy", "ntfy", "Notifications", None),
    ]

    live_statuses = {
        "privacy-shield": privacy_shield_status,
        "everkeep": everkeep_status,
        "netbird": netbird_status,
        "healthchecks": healthchecks_status,
        "uptime-kuma": uptime_kuma_status,
        "beszel": beszel_status,
        "kopia": kopia_status,
        "tasks": tasks_status,
    }

    statuses: list[IntegrationStatus] = []
    for key, name, category, flag in definitions:
        live_status = live_statuses.get(key)
        if live_status is not None:
            state, detail = _normalize_live_status(live_status)
            statuses.append(
                IntegrationStatus(
                    key=key,
                    name=name,
                    category=category,
                    state=state,
                    detail=detail,
                )
            )
        elif flag is None:
            statuses.append(
                IntegrationStatus(
                    key=key,
                    name=name,
                    category=category,
                    state="planned",
                    detail="Adapter not enabled in the initial scaffold.",
                )
            )
        elif _enabled(flag):
            statuses.append(
                IntegrationStatus(
                    key=key,
                    name=name,
                    category=category,
                    state="configured",
                    detail="Enabled by configuration; live adapter validation is still required.",
                )
            )
        else:
            statuses.append(
                IntegrationStatus(
                    key=key,
                    name=name,
                    category=category,
                    state="disabled",
                    detail="Disabled until its approved read-only status source is configured.",
                )
            )

    # Candidate first-party producers appear only when an approved adapter has
    # supplied their read-only status payload. This avoids presenting an absent
    # integration as if it had been configured or observed.
    producer_statuses = [
        ("gateway", "GoreeCloud Gateway", "Gateway", gateway_status),
        ("beacon", "GoreeCloud DNS / Beacon", "DNS", beacon_status),
        ("conduit", "GoreeCloud Network / Conduit", "Network", conduit_status),
    ]
    for key, name, category, payload in producer_statuses:
        if payload is None:
            continue
        state, detail = _producer_availability_status(payload)
        statuses.append(
            IntegrationStatus(
                key=key,
                name=name,
                category=category,
                state=state,
                detail=detail,
            )
        )

    return [asdict(status) for status in statuses]
