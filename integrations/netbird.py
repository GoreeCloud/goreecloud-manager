"""Read-only NetBird REST API adapter for GoreeCloud Manager.

This module intentionally implements visibility only. It uses the documented NetBird
``GET /api/peers`` endpoint and never exposes the configured access token to callers.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import httpx

DEFAULT_TIMEOUT_SECONDS = 5.0
MAX_TIMEOUT_SECONDS = 30.0


@dataclass(frozen=True)
class NetBirdPeer:
    """Normalized peer fields approved for Manager display."""

    peer_id: str
    name: str
    dns_label: str
    ip: str
    ipv6: str
    connected: bool
    last_seen: datetime | None
    os: str
    version: str


@dataclass(frozen=True)
class NetBirdSnapshot:
    """A fail-soft snapshot of the current NetBird integration state."""

    state: str
    detail: str
    peers: tuple[NetBirdPeer, ...] = ()

    @property
    def total(self) -> int:
        return len(self.peers)

    @property
    def connected(self) -> int:
        return sum(1 for peer in self.peers if peer.connected)

    @property
    def disconnected(self) -> int:
        return self.total - self.connected

    def integration_status(self) -> dict[str, str]:
        """Return the normalized registry state without private credentials."""
        return {"state": self.state, "detail": self.detail}


class NetBirdProtocolError(ValueError):
    """Raised when NetBird returns an unexpected response shape."""


def _enabled() -> bool:
    return os.getenv("NETBIRD_ENABLED", "false").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _timeout_seconds() -> float:
    raw = os.getenv("NETBIRD_TIMEOUT_SECONDS", str(DEFAULT_TIMEOUT_SECONDS)).strip()
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


def _normalize_peer(raw: Any) -> NetBirdPeer:
    if not isinstance(raw, dict):
        raise NetBirdProtocolError("NetBird returned a peer entry that was not an object.")

    return NetBirdPeer(
        peer_id=str(raw.get("id") or ""),
        name=str(raw.get("name") or raw.get("dns_label") or "Unnamed peer"),
        dns_label=str(raw.get("dns_label") or ""),
        ip=str(raw.get("ip") or ""),
        ipv6=str(raw.get("ipv6") or ""),
        connected=bool(raw.get("connected", False)),
        last_seen=_parse_timestamp(raw.get("last_seen")),
        os=str(raw.get("os") or "Unknown"),
        version=str(raw.get("version") or ""),
    )


def _healthy_snapshot(payload: Any) -> NetBirdSnapshot:
    if not isinstance(payload, list):
        raise NetBirdProtocolError("NetBird returned an unexpected peers response.")

    peers = tuple(
        sorted(
            (_normalize_peer(item) for item in payload),
            key=lambda peer: (not peer.connected, peer.name.casefold()),
        )
    )
    return NetBirdSnapshot(
        state="healthy",
        detail=f"Live read-only API data verified for {len(peers)} peer(s).",
        peers=peers,
    )


def netbird_snapshot() -> NetBirdSnapshot:
    """Query NetBird and return a normalized, non-secret integration snapshot.

    Failure is intentionally contained so an unavailable NetBird deployment cannot prevent
    the authenticated Manager shell from loading.
    """

    if not _enabled():
        return NetBirdSnapshot(
            state="disabled",
            detail="Disabled until the read-only NetBird integration is explicitly enabled.",
        )

    api_url = os.getenv("NETBIRD_API_URL", "").strip().rstrip("/")
    token = os.getenv("NETBIRD_API_TOKEN", "").strip()

    missing = []
    if not api_url:
        missing.append("NETBIRD_API_URL")
    if not token:
        missing.append("NETBIRD_API_TOKEN")
    if missing:
        return NetBirdSnapshot(
            state="misconfigured",
            detail="Missing required NetBird configuration: " + ", ".join(missing) + ".",
        )

    try:
        response = httpx.get(
            f"{api_url}/peers",
            headers={
                "Accept": "application/json",
                "Authorization": f"Token {token}",
                "User-Agent": "goreecloud-manager/0.1",
            },
            timeout=_timeout_seconds(),
        )
    except httpx.TimeoutException:
        return NetBirdSnapshot(
            state="unavailable",
            detail="NetBird did not respond before the configured timeout.",
        )
    except httpx.RequestError:
        return NetBirdSnapshot(
            state="unavailable",
            detail="Manager could not reach the configured NetBird API endpoint.",
        )

    if response.status_code in {401, 403}:
        return NetBirdSnapshot(
            state="unavailable",
            detail="NetBird rejected the configured read-only API credential.",
        )

    try:
        response.raise_for_status()
    except httpx.HTTPStatusError:
        return NetBirdSnapshot(
            state="unavailable",
            detail=f"NetBird API returned HTTP {response.status_code}.",
        )

    try:
        payload = response.json()
        return _healthy_snapshot(payload)
    except (ValueError, NetBirdProtocolError):
        return NetBirdSnapshot(
            state="unavailable",
            detail="NetBird returned a response Manager could not safely interpret.",
        )
