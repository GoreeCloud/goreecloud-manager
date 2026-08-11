"""Integration registry for GoreeCloud Manager.

The registry intentionally returns configuration state only. Live adapters will be added
individually after their least-privilege credentials, API contracts, failure behavior,
and tests are approved.
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


def integration_statuses() -> list[dict[str, str]]:
    definitions = [
        ("netbird", "NetBird", "Network", "NETBIRD_ENABLED"),
        ("healthchecks", "Healthchecks", "Monitoring", "HEALTHCHECKS_ENABLED"),
        ("docker", "Docker", "Infrastructure", None),
        ("uptime-kuma", "Uptime Kuma", "Monitoring", None),
        ("beszel", "Beszel", "Monitoring", None),
        ("kopia", "Kopia", "Protection", None),
        ("ntfy", "ntfy", "Notifications", None),
    ]

    statuses: list[IntegrationStatus] = []
    for key, name, category, flag in definitions:
        if flag is None:
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
                    detail="Disabled until least-privilege credentials are configured.",
                )
            )

    return [asdict(status) for status in statuses]
