"""Integration registry for GoreeCloud Manager.

The registry reports normalized application-facing state. Live adapters remain responsible
for querying their authoritative systems and returning only approved non-secret fields.
"""

from __future__ import annotations

import os
from dataclasses import asdict, dataclass

from integrations.infrastructure import dns_snapshot, gateway_snapshot, network_snapshot


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
    gateway_status: dict[str, str] | None = None,
    dns_status: dict[str, str] | None = None,
    network_status: dict[str, str] | None = None,
    netbird_status: dict[str, str] | None = None,
    healthchecks_status: dict[str, str] | None = None,
    uptime_kuma_status: dict[str, str] | None = None,
    beszel_status: dict[str, str] | None = None,
    kopia_status: dict[str, str] | None = None,
    tasks_status: dict[str, str] | None = None,
    privacy_shield_status: dict[str, str] | None = None,
    everkeep_status: dict[str, str] | None = None,
) -> list[dict[str, str]]:
    """Return normalized registry state without exposing infrastructure credentials.

    Gateway, DNS, and Network use bounded local Infrastructure Status v1 documents.
    They are loaded here when the caller does not supply a precomputed normalized state,
    so they do not consume Manager's remote-integration worker pool.
    """

    if gateway_status is None:
        gateway_status = gateway_snapshot().integration_status()
    if dns_status is None:
        dns_status = dns_snapshot().integration_status()
    if network_status is None:
        network_status = network_snapshot().integration_status()

    definitions = [
        ("privacy-shield", "Privacy Shield", "Privacy", None),
        ("everkeep", "Everkeep", "Protection / Continuity", "EVERKEEP_ENABLED"),
        ("goreecloud-gateway", "GoreeCloud Gateway", "Infrastructure", None),
        ("goreecloud-dns", "GoreeCloud DNS", "Network / DNS", None),
        ("goreecloud-network", "GoreeCloud Network", "Network", None),
        ("netbird", "NetBird", "Network / Transitional", "NETBIRD_ENABLED"),
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
        "goreecloud-gateway": gateway_status,
        "goreecloud-dns": dns_status,
        "goreecloud-network": network_status,
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
