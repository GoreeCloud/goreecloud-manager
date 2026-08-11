"""Read-only Beszel status-artifact integration for GoreeCloud Manager.

Beszel remains authoritative for resource monitoring. Manager reads only a sanitized JSON
artifact produced by a delegated host-side collector. The Manager process never receives
a Beszel password/auth token, Beszel application data, agent credentials, or Docker access.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DEFAULT_STATUS_PATH = "/app/integrations/beszel/status.json"
DEFAULT_ARTIFACT_MAX_AGE_SECONDS = 15 * 60
DEFAULT_DATA_MAX_AGE_SECONDS = 30 * 60
MAX_AGE_SECONDS = 24 * 60 * 60
SUPPORTED_SCHEMA_VERSION = 1
COLLECTOR_STATES = {"ok", "auth_error", "unavailable", "error"}


def _enabled() -> bool:
    return os.getenv("BESZEL_ENABLED", "false").strip().lower() in {
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


def _number(value: Any, *, minimum: float = 0) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    result = float(value)
    if result < minimum:
        return None
    return result


def _integer(value: Any, *, minimum: int = 0) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
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


def _bytes_label(value: int | None) -> str:
    if value is None:
        return "Unknown"

    size = float(value)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if size < 1024 or unit == "TiB":
            if unit == "B":
                return f"{int(size)} {unit}"
            return f"{size:.1f} {unit}"
        size /= 1024

    return f"{value} B"


def _gb_label(value: float | None) -> str:
    return "Unknown" if value is None else f"{value:.2f} GB"


def _percent_label(value: float | None) -> str:
    return "Unknown" if value is None else f"{value:.1f}%"


@dataclass(frozen=True)
class BeszelDetails:
    hostname: str
    kernel: str
    cores: int | None
    threads: int | None
    cpu_model: str
    os_name: str
    architecture: str
    memory_bytes: int | None
    podman: bool

    @property
    def memory_label(self) -> str:
        return _bytes_label(self.memory_bytes)


@dataclass(frozen=True)
class BeszelStats:
    observed_at: datetime
    cpu_percent: float | None
    load_average: tuple[float, ...]
    memory_total_gb: float | None
    memory_used_gb: float | None
    memory_percent: float | None
    swap_total_gb: float | None
    swap_used_gb: float | None
    disk_total_gb: float | None
    disk_used_gb: float | None
    disk_percent: float | None
    network_sent_bytes: int | None
    network_recv_bytes: int | None
    temperatures: tuple[tuple[str, float], ...]

    @property
    def cpu_label(self) -> str:
        return _percent_label(self.cpu_percent)

    @property
    def memory_label(self) -> str:
        if self.memory_used_gb is None or self.memory_total_gb is None:
            return "Unknown"
        return f"{self.memory_used_gb:.2f} / {self.memory_total_gb:.2f} GB"

    @property
    def memory_percent_label(self) -> str:
        return _percent_label(self.memory_percent)

    @property
    def swap_label(self) -> str:
        if self.swap_used_gb is None or self.swap_total_gb is None:
            return "Unknown"
        return f"{self.swap_used_gb:.2f} / {self.swap_total_gb:.2f} GB"

    @property
    def disk_label(self) -> str:
        if self.disk_used_gb is None or self.disk_total_gb is None:
            return "Unknown"
        return f"{self.disk_used_gb:.2f} / {self.disk_total_gb:.2f} GB"

    @property
    def disk_percent_label(self) -> str:
        return _percent_label(self.disk_percent)

    @property
    def network_sent_label(self) -> str:
        return _bytes_label(self.network_sent_bytes)

    @property
    def network_recv_label(self) -> str:
        return _bytes_label(self.network_recv_bytes)

    @property
    def load_average_label(self) -> str:
        return " / ".join(f"{value:.2f}" for value in self.load_average) or "Unknown"


@dataclass(frozen=True)
class BeszelContainer:
    name: str
    state: str
    health: str
    cpu_percent: float | None
    memory_gb: float | None
    network_sent_bytes: int | None
    network_recv_bytes: int | None

    @property
    def cpu_label(self) -> str:
        return _percent_label(self.cpu_percent)

    @property
    def memory_label(self) -> str:
        return _gb_label(self.memory_gb)

    @property
    def network_label(self) -> str:
        if self.network_sent_bytes is None and self.network_recv_bytes is None:
            return "Unknown"
        return (
            f"TX {_bytes_label(self.network_sent_bytes)} / "
            f"RX {_bytes_label(self.network_recv_bytes)}"
        )

    @property
    def attention(self) -> bool:
        return not self.state.lower().startswith("up") or self.health == "unhealthy"


@dataclass(frozen=True)
class BeszelStatus:
    state: str
    detail: str
    generated_at: datetime | None = None
    artifact_age_seconds: int | None = None
    collector_state: str = ""
    collector_checked_at: datetime | None = None
    beszel_version: str = ""
    source_name: str = ""
    source_status: str = ""
    source_updated_at: datetime | None = None
    agent_version: str = ""
    uptime_seconds: int | None = None
    stats: BeszelStats | None = None
    details: BeszelDetails | None = None
    containers: tuple[BeszelContainer, ...] = ()

    @property
    def artifact_age_label(self) -> str:
        return _duration_label(self.artifact_age_seconds)

    @property
    def uptime_label(self) -> str:
        return _duration_label(self.uptime_seconds)

    @property
    def container_total(self) -> int:
        return len(self.containers)

    @property
    def container_attention(self) -> int:
        return sum(1 for container in self.containers if container.attention)

    @property
    def container_healthy(self) -> int:
        return self.container_total - self.container_attention

    def integration_status(self) -> dict[str, str]:
        return {"state": self.state, "detail": self.detail}


def _unavailable(detail: str) -> BeszelStatus:
    return BeszelStatus(state="unavailable", detail=detail)


def _parse_details(value: Any) -> BeszelDetails | None:
    if not isinstance(value, dict):
        return None

    text_fields = {
        key: value.get(key, "")
        for key in ("hostname", "kernel", "cpu_model", "os_name", "architecture")
    }
    if any(not isinstance(item, str) for item in text_fields.values()):
        return None

    podman = value.get("podman", False)
    if not isinstance(podman, bool):
        return None

    return BeszelDetails(
        hostname=text_fields["hostname"].strip(),
        kernel=text_fields["kernel"].strip(),
        cores=_integer(value.get("cores")),
        threads=_integer(value.get("threads")),
        cpu_model=text_fields["cpu_model"].strip(),
        os_name=text_fields["os_name"].strip(),
        architecture=text_fields["architecture"].strip(),
        memory_bytes=_integer(value.get("memory_bytes")),
        podman=podman,
    )


def _parse_stats(value: Any) -> BeszelStats | None:
    if not isinstance(value, dict):
        return None

    observed_at = _parse_timestamp(value.get("observed_at"))
    if observed_at is None:
        return None

    load_average = value.get("load_average", [])
    if not isinstance(load_average, list):
        return None
    parsed_load: list[float] = []
    for item in load_average[:3]:
        number = _number(item)
        if number is None:
            return None
        parsed_load.append(number)

    temperatures = value.get("temperatures", {})
    if not isinstance(temperatures, dict):
        return None
    parsed_temperatures: list[tuple[str, float]] = []
    for key, raw in sorted(temperatures.items()):
        if not isinstance(key, str):
            return None
        number = _number(raw, minimum=-273.15)
        if number is None:
            return None
        parsed_temperatures.append((key.strip(), number))

    network = value.get("network", {})
    if not isinstance(network, dict):
        return None

    return BeszelStats(
        observed_at=observed_at,
        cpu_percent=_number(value.get("cpu_percent")),
        load_average=tuple(parsed_load),
        memory_total_gb=_number(value.get("memory_total_gb")),
        memory_used_gb=_number(value.get("memory_used_gb")),
        memory_percent=_number(value.get("memory_percent")),
        swap_total_gb=_number(value.get("swap_total_gb")),
        swap_used_gb=_number(value.get("swap_used_gb")),
        disk_total_gb=_number(value.get("disk_total_gb")),
        disk_used_gb=_number(value.get("disk_used_gb")),
        disk_percent=_number(value.get("disk_percent")),
        network_sent_bytes=_integer(network.get("sent_bytes")),
        network_recv_bytes=_integer(network.get("recv_bytes")),
        temperatures=tuple(parsed_temperatures),
    )


def _parse_container(value: Any) -> BeszelContainer | None:
    if not isinstance(value, dict):
        return None

    name = value.get("name")
    state = value.get("state")
    health = value.get("health", "unknown")
    if not isinstance(name, str) or not name.strip() or not isinstance(state, str):
        return None
    if health not in {"none", "starting", "healthy", "unhealthy", "unknown"}:
        return None

    network = value.get("network", {})
    if not isinstance(network, dict):
        return None

    return BeszelContainer(
        name=name.strip(),
        state=state.strip() or "Unknown",
        health=health,
        cpu_percent=_number(value.get("cpu_percent")),
        memory_gb=_number(value.get("memory_gb")),
        network_sent_bytes=_integer(network.get("sent_bytes")),
        network_recv_bytes=_integer(network.get("recv_bytes")),
    )


def beszel_status(*, now: datetime | None = None) -> BeszelStatus:
    """Read and normalize the delegated Beszel status artifact."""

    if not _enabled():
        return BeszelStatus(
            state="disabled",
            detail="Native Beszel resource visibility is disabled.",
        )

    status_path = os.getenv("BESZEL_STATUS_PATH", DEFAULT_STATUS_PATH).strip()
    if not status_path:
        return BeszelStatus(
            state="misconfigured",
            detail="Beszel status artifact path is not configured.",
        )

    try:
        raw = Path(status_path).read_text(encoding="utf-8")
    except FileNotFoundError:
        return _unavailable("Beszel status artifact is not available.")
    except OSError:
        return _unavailable("Manager could not read the Beszel status artifact.")

    try:
        payload = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return _unavailable("Beszel status artifact is malformed.")

    if not isinstance(payload, dict):
        return _unavailable("Beszel status artifact has an unexpected structure.")
    if payload.get("schema_version") != SUPPORTED_SCHEMA_VERSION:
        return _unavailable("Beszel status artifact schema is not supported.")

    generated_at = _parse_timestamp(payload.get("generated_at"))
    collector = payload.get("collector")
    if generated_at is None or not isinstance(collector, dict):
        return _unavailable("Beszel status artifact is missing required status fields.")

    collector_state = collector.get("state")
    collector_checked_at = _parse_timestamp(collector.get("checked_at"))
    if collector_state not in COLLECTOR_STATES or collector_checked_at is None:
        return _unavailable("Beszel status artifact collector state is invalid.")

    source = payload.get("source")
    stats_raw = payload.get("stats")
    details_raw = payload.get("details")
    containers_raw = payload.get("containers", [])

    has_data = isinstance(source, dict) and isinstance(stats_raw, dict) and isinstance(details_raw, dict)
    if not has_data:
        if collector_state == "auth_error":
            return _unavailable("Delegated Beszel collector authentication failed.")
        if collector_state == "unavailable":
            return _unavailable("Delegated Beszel collector could not reach Beszel.")
        if collector_state == "error":
            return _unavailable("Delegated Beszel collector could not refresh Beszel data.")
        return _unavailable("Beszel status artifact does not contain resource data.")

    source_name = source.get("name", "")
    source_status = source.get("status", "")
    source_updated_at = _parse_timestamp(source.get("updated_at"))
    agent_version = source.get("agent_version", "")
    beszel_version = source.get("beszel_version", "")
    uptime_seconds = _integer(source.get("uptime_seconds"))
    if (
        not isinstance(source_name, str)
        or not source_name.strip()
        or not isinstance(source_status, str)
        or not source_status.strip()
        or source_updated_at is None
        or not isinstance(agent_version, str)
        or not isinstance(beszel_version, str)
        or uptime_seconds is None
    ):
        return _unavailable("Beszel status artifact source data is malformed.")

    stats = _parse_stats(stats_raw)
    details = _parse_details(details_raw)
    if stats is None or details is None or not isinstance(containers_raw, list):
        return _unavailable("Beszel status artifact resource data is malformed.")

    containers: list[BeszelContainer] = []
    for item in containers_raw:
        container = _parse_container(item)
        if container is None:
            return _unavailable("Beszel status artifact container data is malformed.")
        containers.append(container)

    current = (now or datetime.now(UTC)).astimezone(UTC)
    artifact_age = _age_seconds(generated_at, now=current)
    data_age = _age_seconds(stats.observed_at, now=current)
    artifact_max_age = _bounded_seconds(
        "BESZEL_STATUS_MAX_AGE_SECONDS",
        DEFAULT_ARTIFACT_MAX_AGE_SECONDS,
    )
    data_max_age = _bounded_seconds(
        "BESZEL_DATA_MAX_AGE_SECONDS",
        DEFAULT_DATA_MAX_AGE_SECONDS,
    )

    concerns: list[str] = []
    if collector_state == "auth_error":
        concerns.append("latest delegated collector authentication failed")
    elif collector_state == "unavailable":
        concerns.append("latest delegated collector run could not reach Beszel")
    elif collector_state == "error":
        concerns.append("latest delegated collector run failed")

    if generated_at > current:
        concerns.append("status artifact timestamp is in the future")
    elif artifact_age is not None and artifact_age > artifact_max_age:
        concerns.append("status artifact is stale")

    if stats.observed_at > current:
        concerns.append("resource observation timestamp is in the future")
    elif data_age is not None and data_age > data_max_age:
        concerns.append("resource data is stale")

    if source_status.lower() != "up":
        concerns.append(f"Beszel reports system state {source_status}")

    state = "degraded" if concerns else "healthy"
    if concerns:
        detail = "Native Beszel resource data verified; " + "; ".join(concerns) + "."
    else:
        detail = (
            "Native Beszel resource data verified from the delegated read-only artifact "
            f"for {len(containers)} container(s)."
        )

    return BeszelStatus(
        state=state,
        detail=detail,
        generated_at=generated_at,
        artifact_age_seconds=artifact_age,
        collector_state=collector_state,
        collector_checked_at=collector_checked_at,
        beszel_version=beszel_version.strip(),
        source_name=source_name.strip(),
        source_status=source_status.strip(),
        source_updated_at=source_updated_at,
        agent_version=agent_version.strip(),
        uptime_seconds=uptime_seconds,
        stats=stats,
        details=details,
        containers=tuple(sorted(containers, key=lambda item: item.name.casefold())),
    )
