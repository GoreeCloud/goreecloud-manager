"""Bounded live GoreeCloud Mesh event consumer for Manager refresh signaling.

This adapter consumes only the closed GoreeCloud Mesh lifecycle-event contract and
converts accepted events into a minimal refresh signal for Manager's read-only Platform
Overview. The Mesh event itself is never treated as platform truth: after a signal the
browser reloads the Platform Overview, which re-reads the authoritative normalized
Platform Registry through the separate ``mesh.platform-registry.read`` path.

The event credential is deliberately separate from the Platform Registry credential so
Manager can be granted ``mesh.events.read`` without broadening either token. No replay,
retention, acknowledgement, retry guarantee, or producer-domain authority is introduced
by this adapter.
"""

from __future__ import annotations

import json
import os
import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator
from urllib.parse import urlparse

import httpx

EVENT_STREAM_PATH = "/v1/events/stream"
EVENT_SCHEMA = "goreecloud.mesh.event.v1"
SERVICE_UPSERTED = "mesh.service.upserted.v1"
RELATIONSHIP_UPSERTED = "mesh.relationship.upserted.v1"
EVENT_TYPES = (SERVICE_UPSERTED, RELATIONSHIP_UPSERTED)
EXPECTED_EVENT_FIELDS = {
    "schema",
    "id",
    "type",
    "source",
    "subject",
    "data",
    "created_at",
    "authority_transfer",
}
HEALTH_STATES = {"unknown", "healthy", "degraded", "unavailable"}
EVENT_ID_PATTERN = re.compile(r"^evt-[1-9][0-9]*$")
MAX_CREDENTIAL_LENGTH = 16_384
MAX_EVENT_IDENTITY_CHARS = 128
MAX_EVENT_VALUE_CHARS = 256
MAX_STREAM_BYTES = 128 * 1024
DEFAULT_BUFFER_SIZE = 8
MAX_BUFFER_SIZE = 64
DEFAULT_WINDOW_SECONDS = 5
MAX_WINDOW_SECONDS = 10


@dataclass(frozen=True)
class MeshEventStreamStatus:
    state: str
    detail: str


@dataclass(frozen=True)
class _MeshEventStreamConfig:
    url: str
    token: str
    buffer_size: int
    window_seconds: int


class MeshEventProtocolError(ValueError):
    """Raised when the upstream event stream violates the accepted closed contract."""


def _enabled() -> bool:
    return os.getenv("MESH_EVENTS_ENABLED", "false").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _bounded_int(name: str, default: int, maximum: int) -> tuple[int | None, str | None]:
    raw = os.getenv(name, str(default)).strip()
    try:
        value = int(raw)
    except ValueError:
        return None, f"{name} must be an integer from 1 to {maximum}."
    if value < 1 or value > maximum:
        return None, f"{name} must be an integer from 1 to {maximum}."
    return value, None


def _validate_token(value: str) -> tuple[str | None, str | None]:
    token = value.strip()
    if not token:
        return None, "The configured Mesh event access token is empty."
    if len(token) > MAX_CREDENTIAL_LENGTH:
        return None, "The configured Mesh event access token exceeds the approved size bound."
    if "\r" in token or "\n" in token:
        return None, "The configured Mesh event access token contains invalid line breaks."
    return token, None


def _configured_token() -> tuple[str | None, str | None]:
    direct = os.getenv("MESH_EVENTS_ACCESS_TOKEN", "")
    file_path = os.getenv("MESH_EVENTS_ACCESS_TOKEN_FILE", "").strip()
    if direct.strip() and file_path:
        return None, "Set only one Mesh event access-token source."
    if file_path:
        try:
            token = Path(file_path).read_text(encoding="utf-8")
        except OSError:
            return None, "The configured Mesh event access-token file could not be read."
        return _validate_token(token)
    if direct.strip():
        return _validate_token(direct)
    return None, "Missing MESH_EVENTS_ACCESS_TOKEN or MESH_EVENTS_ACCESS_TOKEN_FILE."


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
    return f"{base_url}{EVENT_STREAM_PATH}", None


def _stream_config() -> tuple[_MeshEventStreamConfig | None, str | None]:
    url, url_error = _api_url()
    token, token_error = _configured_token()
    buffer_size, buffer_error = _bounded_int(
        "MESH_EVENTS_BUFFER_SIZE",
        DEFAULT_BUFFER_SIZE,
        MAX_BUFFER_SIZE,
    )
    window_seconds, window_error = _bounded_int(
        "MESH_EVENTS_WINDOW_SECONDS",
        DEFAULT_WINDOW_SECONDS,
        MAX_WINDOW_SECONDS,
    )
    errors = [
        error
        for error in (url_error, token_error, buffer_error, window_error)
        if error is not None
    ]
    if errors:
        return None, " ".join(errors)
    assert url is not None
    assert token is not None
    assert buffer_size is not None
    assert window_seconds is not None
    return (
        _MeshEventStreamConfig(
            url=url,
            token=token,
            buffer_size=buffer_size,
            window_seconds=window_seconds,
        ),
        None,
    )


def mesh_event_stream_status() -> MeshEventStreamStatus:
    """Return non-secret local configuration status for Platform Overview rendering."""

    if not _enabled():
        return MeshEventStreamStatus(
            state="disabled",
            detail="Live Mesh refresh signaling is disabled.",
        )
    _config, error = _stream_config()
    if error:
        return MeshEventStreamStatus(
            state="misconfigured",
            detail=error,
        )
    return MeshEventStreamStatus(
        state="configured",
        detail=(
            "Bounded live Mesh refresh signaling is configured. Runtime availability is "
            "established only when the browser opens the authenticated Manager stream."
        ),
    )


def _validate_text(value: Any, field: str, maximum: int) -> str:
    if not isinstance(value, str):
        raise MeshEventProtocolError(f"Mesh event {field} must be a string.")
    text = value.strip()
    if not text or len(text) > maximum:
        raise MeshEventProtocolError(f"Mesh event {field} is blank or oversized.")
    if any(unicodedata.category(char).startswith("C") for char in text):
        raise MeshEventProtocolError(f"Mesh event {field} contains control characters.")
    return text


def _timestamp(value: Any) -> datetime:
    text = _validate_text(value, "created_at", MAX_EVENT_VALUE_CHARS)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise MeshEventProtocolError("Mesh event created_at is invalid.") from exc
    if parsed.tzinfo is None:
        raise MeshEventProtocolError("Mesh event created_at must include a timezone.")
    return parsed


def _validate_event_payload(payload: Any, event_name: str, *, now: datetime) -> dict[str, str]:
    if not isinstance(payload, dict) or set(payload) != EXPECTED_EVENT_FIELDS:
        raise MeshEventProtocolError("Mesh event envelope is not the closed v1 shape.")
    if payload.get("schema") != EVENT_SCHEMA:
        raise MeshEventProtocolError("Mesh event schema is unsupported.")
    if payload.get("authority_transfer") is not False:
        raise MeshEventProtocolError("Mesh event attempted to transfer authority.")

    event_type = _validate_text(payload.get("type"), "type", MAX_EVENT_VALUE_CHARS)
    if event_type not in EVENT_TYPES or event_type != event_name:
        raise MeshEventProtocolError("Mesh event type is unsupported or mismatched.")
    event_id = _validate_text(payload.get("id"), "id", MAX_EVENT_IDENTITY_CHARS)
    if not EVENT_ID_PATTERN.fullmatch(event_id):
        raise MeshEventProtocolError("Mesh event id is invalid.")

    source = _validate_text(payload.get("source"), "source", MAX_EVENT_IDENTITY_CHARS)
    subject = _validate_text(payload.get("subject"), "subject", MAX_EVENT_IDENTITY_CHARS)
    created_at = _timestamp(payload.get("created_at"))
    if created_at > now:
        raise MeshEventProtocolError("Mesh event is timestamped in the future.")

    data = payload.get("data")
    if not isinstance(data, dict):
        raise MeshEventProtocolError("Mesh event data must be an object.")

    if event_type == SERVICE_UPSERTED:
        if source != subject or set(data) != {"health"}:
            raise MeshEventProtocolError("Mesh service lifecycle event binding is invalid.")
        health = _validate_text(data.get("health"), "data.health", MAX_EVENT_VALUE_CHARS)
        if health not in HEALTH_STATES:
            raise MeshEventProtocolError("Mesh service lifecycle health is unsupported.")
    elif event_type == RELATIONSHIP_UPSERTED:
        if set(data) != {"target", "type"}:
            raise MeshEventProtocolError("Mesh relationship lifecycle event data is invalid.")
        _validate_text(data.get("target"), "data.target", MAX_EVENT_IDENTITY_CHARS)
        _validate_text(data.get("type"), "data.type", MAX_EVENT_VALUE_CHARS)

    # The browser receives only the event type needed to trigger a fresh Platform
    # Registry read. Source, subject, health, relationship metadata, event id, and the
    # Mesh credential remain server-side and are not copied into the page event stream.
    return {"type": event_type}


def _parse_sse_lines(lines: Iterator[str]) -> Iterator[dict[str, str]]:
    event_name: str | None = None
    data_lines: list[str] = []
    observed_bytes = 0

    for line in lines:
        observed_bytes += len(line.encode("utf-8")) + 1
        if observed_bytes > MAX_STREAM_BYTES:
            raise MeshEventProtocolError("Mesh event stream exceeded the approved byte bound.")

        if line == "":
            if event_name is not None or data_lines:
                if event_name is None or not data_lines:
                    raise MeshEventProtocolError("Mesh event stream frame is incomplete.")
                try:
                    payload = json.loads("\n".join(data_lines))
                except json.JSONDecodeError as exc:
                    raise MeshEventProtocolError("Mesh event data is not valid JSON.") from exc
                yield _validate_event_payload(payload, event_name, now=datetime.now(timezone.utc))
            event_name = None
            data_lines = []
            continue

        if line.startswith(":"):
            continue

        field, separator, value = line.partition(":")
        if not separator:
            raise MeshEventProtocolError("Mesh event stream contains an unsupported SSE field.")
        if value.startswith(" "):
            value = value[1:]

        if field == "event":
            if event_name is not None:
                raise MeshEventProtocolError("Mesh event stream contains duplicate event fields.")
            event_name = value
        elif field == "data":
            data_lines.append(value)
        else:
            # In particular, reject id/retry fields. The current Mesh transport is
            # explicitly non-replayable and must not acquire cursor semantics here.
            raise MeshEventProtocolError("Mesh event stream contains an unsupported SSE field.")

    if event_name is not None or data_lines:
        raise MeshEventProtocolError("Mesh event stream ended with an incomplete frame.")


def iter_mesh_event_refresh_signals() -> Iterator[str]:
    """Yield sanitized same-origin SSE signals for accepted Mesh lifecycle events.

    Network, authorization, HTTP, content-type, and contract failures terminate the
    current best-effort stream without reflecting upstream error text or credentials.
    Browser EventSource reconnection remains live-only; no replay cursor is supplied.
    """

    if not _enabled():
        return
    config, error = _stream_config()
    if error or config is None:
        return

    headers = {
        "Accept": "text/event-stream",
        "Authorization": f"Bearer {config.token}",
        "Cache-Control": "no-store",
        "User-Agent": "goreecloud-manager/0.1",
    }
    params = [
        ("type", SERVICE_UPSERTED),
        ("type", RELATIONSHIP_UPSERTED),
        ("buffer", str(config.buffer_size)),
        ("window_seconds", str(config.window_seconds)),
    ]
    timeout = httpx.Timeout(float(config.window_seconds + 2))

    try:
        with httpx.stream(
            "GET",
            config.url,
            params=params,
            headers=headers,
            timeout=timeout,
        ) as response:
            if response.status_code != 200:
                return
            content_type = response.headers.get("content-type", "").lower()
            if not content_type.startswith("text/event-stream"):
                return
            try:
                for signal in _parse_sse_lines(iter(response.iter_lines())):
                    encoded = json.dumps(signal, separators=(",", ":"), sort_keys=True)
                    yield f"event: platform-update\ndata: {encoded}\n\n"
            except (MeshEventProtocolError, UnicodeError):
                return
    except (httpx.TimeoutException, httpx.RequestError):
        return
