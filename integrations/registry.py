"""Integration registry for GoreeCloud Manager.

The registry reports normalized application-facing state. Live adapters remain responsible
for querying their authoritative systems and returning only approved non-secret fields.
"""

from __future__ import annotations

import os
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class IntegrationStatus:
    key: str
    name: str
    category: str
    state: str
    detail: str


def _enabled(name: str) -> bool:
    return os.getenv(name, "false").strip().lower() in {"1", "true", "yes", "on"}


def integration_statuses(
    *,
    netbird_status: dict[str, str] | None = None,
    healthchecks_status: dict[str, str] | None = None,
    uptime_kuma_status: dict[str, str] | None = None,
    beszel_status: dict[str, str] | None = None,
    kopia_status: dict[str, str] | None = None,
    tasks_status: dict[str, str] | None = None,
    privacy_shield_status: dict[str, str] | None = None,
    everkeep_status: dict[str, str] | None = None,
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
            statuses.append(
                IntegrationStatus(
                    key=key,
                    name=name,
                    category=category,
                    state=live_status["state"],
                    detail=live_status["detail"],
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

    return [asdict(status) for status in statuses]
