"""Read-only Uptime Kuma Prometheus metrics adapter for GoreeCloud Manager.

The adapter uses Uptime Kuma's metrics-only API-key authentication and retains only
approved non-secret monitor fields. Raw target URLs, hostnames, ports, request
configuration, and upstream response bodies are never returned to callers.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import httpx

DEFAULT_TIMEOUT_SECONDS = 5.0
MAX_TIMEOUT_SECONDS = 30.0

_STATUS_MAP = {
    0: "down",
    1: "up",
    2: "pending",
    3: "maintenance",
}

_SAMPLE_RE = re.compile(
    r"^(?P<metric>[a-zA-Z_:][a-zA-Z0-9_:]*)"
    r"(?:\{(?P<labels>.*)\})?\s+"
    r"(?P<value>[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?)"
    r"(?:\s+\d+)?$"
)
_LABEL_RE = re.compile(r'([a-zA-Z_][a-zA-Z0-9_]*)="((?:\\.|[^"])*)"')


@dataclass(frozen=True)
class UptimeKumaMonitor:
    """Normalized Uptime Kuma fields approved for Manager display."""

    name: str
    monitor_type: str
    state: str
    response_time_ms: float | None = None

    @property
    def state_label(self) -> str:
        return self.state.replace("-", " ").title()

    @property
    def response_time_label(self) -> str:
        if self.response_time_ms is None:
            return "Not reported"
        if self.response_time_ms.is_integer():
            return f"{int(self.response_time_ms)} ms"
        return f"{self.response_time_ms:.1f} ms"


@dataclass(frozen=True)
class UptimeKumaSnapshot:
    """Fail-soft snapshot of current Uptime Kuma monitor metrics."""

    state: str
    detail: str
    observed_at: datetime | None = None
    monitors: tuple[UptimeKumaMonitor, ...] = ()

    @property
    def total(self) -> int:
        return len(self.monitors)

    def count(self, state: str) -> int:
        return sum(1 for monitor in self.monitors if monitor.state == state)

    @property
    def up(self) -> int:
        return self.count("up")

    @property
    def down(self) -> int:
        return self.count("down")

    @property
    def pending(self) -> int:
        return self.count("pending")

    @property
    def maintenance(self) -> int:
        return self.count("maintenance")

    @property
    def unknown(self) -> int:
        return self.count("unknown")

    @property
    def attention(self) -> int:
        return self.down + self.pending + self.unknown

    def integration_status(self) -> dict[str, str]:
        return {"state": self.state, "detail": self.detail}


class UptimeKumaProtocolError(ValueError):
    """Raised when Uptime Kuma metrics cannot be safely normalized."""


def _enabled() -> bool:
    return os.getenv("UPTIME_KUMA_ENABLED", "false").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _timeout_seconds() -> float:
    raw = os.getenv(
        "UPTIME_KUMA_TIMEOUT_SECONDS", str(DEFAULT_TIMEOUT_SECONDS)
    ).strip()
    try:
        value = float(raw)
    except ValueError:
        return DEFAULT_TIMEOUT_SECONDS
    if value <= 0:
        return DEFAULT_TIMEOUT_SECONDS
    return min(value, MAX_TIMEOUT_SECONDS)


def _unescape_label(value: str) -> str:
    # Prometheus label escaping is intentionally handled narrowly. We only retain
    # approved display labels, so newline and quoted-string escaping are sufficient.
    return value.replace(r"\n", " ").replace(r'\"', '"').strip()


def _labels(raw: str) -> dict[str, str]:
    return {
        match.group(1): _unescape_label(match.group(2))
        for match in _LABEL_RE.finditer(raw)
    }


def _safe_float(value: Any) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if parsed < 0:
        return None
    return parsed


def _parse_metrics(text: str, *, observed_at: datetime) -> UptimeKumaSnapshot:
    statuses: dict[tuple[str, str], str] = {}
    response_times: dict[tuple[str, str], float] = {}

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        match = _SAMPLE_RE.match(line)
        if not match:
            continue

        metric = match.group("metric")
        if metric not in {"monitor_status", "monitor_response_time"}:
            continue

        parsed_labels = _labels(match.group("labels") or "")
        name = parsed_labels.get("monitor_name", "").strip()
        monitor_type = parsed_labels.get("monitor_type", "").strip()
        if not name:
            continue

        key = (name, monitor_type)
        value = match.group("value")

        if metric == "monitor_status":
            try:
                raw_status = int(float(value))
            except (TypeError, ValueError) as exc:
                raise UptimeKumaProtocolError(
                    "Uptime Kuma returned an invalid monitor status value."
                ) from exc
            statuses[key] = _STATUS_MAP.get(raw_status, "unknown")
        else:
            response_time = _safe_float(value)
            if response_time is not None:
                response_times[key] = response_time

    monitors = tuple(
        sorted(
            (
                UptimeKumaMonitor(
                    name=name,
                    monitor_type=monitor_type or "unknown",
                    state=state,
                    response_time_ms=response_times.get((name, monitor_type)),
                )
                for (name, monitor_type), state in statuses.items()
            ),
            key=lambda monitor: (monitor.state != "down", monitor.name.casefold()),
        )
    )

    if not monitors:
        return UptimeKumaSnapshot(
            state="degraded",
            detail=(
                "Uptime Kuma metrics were reachable but reported no monitor "
                "status samples."
            ),
            observed_at=observed_at,
        )

    down = sum(1 for monitor in monitors if monitor.state == "down")
    pending = sum(1 for monitor in monitors if monitor.state == "pending")
    unknown = sum(1 for monitor in monitors if monitor.state == "unknown")
    maintenance = sum(1 for monitor in monitors if monitor.state == "maintenance")
    attention = down + pending + unknown

    if attention:
        return UptimeKumaSnapshot(
            state="degraded",
            detail=(
                f"Live metrics verified for {len(monitors)} monitor(s); "
                f"{attention} require attention."
            ),
            observed_at=observed_at,
            monitors=monitors,
        )

    suffix = f"; {maintenance} in maintenance" if maintenance else ""
    return UptimeKumaSnapshot(
        state="healthy",
        detail=(
            f"Live read-only metrics verified for {len(monitors)} monitor(s){suffix}."
        ),
        observed_at=observed_at,
        monitors=monitors,
    )


def uptime_kuma_snapshot() -> UptimeKumaSnapshot:
    """Query Uptime Kuma metrics and return only approved monitor visibility."""

    if not _enabled():
        return UptimeKumaSnapshot(
            state="disabled",
            detail=(
                "Disabled until the read-only Uptime Kuma metrics integration is "
                "explicitly enabled."
            ),
        )

    metrics_url = os.getenv("UPTIME_KUMA_METRICS_URL", "").strip()
    api_key = os.getenv("UPTIME_KUMA_API_KEY", "").strip()

    missing = []
    if not metrics_url:
        missing.append("UPTIME_KUMA_METRICS_URL")
    if not api_key:
        missing.append("UPTIME_KUMA_API_KEY")
    if missing:
        return UptimeKumaSnapshot(
            state="misconfigured",
            detail=(
                "Missing required Uptime Kuma configuration: "
                + ", ".join(missing)
                + "."
            ),
        )

    observed_at = datetime.now(UTC)

    try:
        response = httpx.get(
            metrics_url,
            auth=httpx.BasicAuth("", api_key),
            headers={
                "Accept": "text/plain",
                "User-Agent": "goreecloud-manager/0.1",
            },
            timeout=_timeout_seconds(),
        )
    except httpx.TimeoutException:
        return UptimeKumaSnapshot(
            state="unavailable",
            detail="Uptime Kuma did not respond before the configured timeout.",
            observed_at=observed_at,
        )
    except httpx.RequestError:
        return UptimeKumaSnapshot(
            state="unavailable",
            detail="Manager could not reach the configured Uptime Kuma metrics endpoint.",
            observed_at=observed_at,
        )

    if response.status_code == 401:
        return UptimeKumaSnapshot(
            state="unavailable",
            detail="Uptime Kuma rejected the configured metrics API key.",
            observed_at=observed_at,
        )

    if response.status_code == 403:
        return UptimeKumaSnapshot(
            state="unavailable",
            detail="Uptime Kuma denied access to the configured metrics endpoint.",
            observed_at=observed_at,
        )

    try:
        response.raise_for_status()
    except httpx.HTTPStatusError:
        return UptimeKumaSnapshot(
            state="unavailable",
            detail=f"Uptime Kuma metrics returned HTTP {response.status_code}.",
            observed_at=observed_at,
        )

    try:
        return _parse_metrics(response.text, observed_at=observed_at)
    except (ValueError, UptimeKumaProtocolError):
        return UptimeKumaSnapshot(
            state="unavailable",
            detail="Uptime Kuma returned metrics Manager could not safely interpret.",
            observed_at=observed_at,
        )
