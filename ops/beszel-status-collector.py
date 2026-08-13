#!/usr/bin/env python3
"""Produce GoreeCloud Manager's sanitized read-only Beszel status artifact.

The collector runs outside the Manager container. It authenticates with a dedicated Beszel
``readonly`` account, verifies that exactly one approved system is visible, performs only
approved data reads after authentication, and writes a small non-secret JSON artifact.
Beszel credentials and PocketBase auth tokens never enter the artifact.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1
DEFAULT_STATUS_PATH = Path(
    "/srv/docker/appdata/goreecloud-manager/integrations/beszel/status.json"
)
DEFAULT_CREDENTIALS_PATH = Path(
    "/srv/docker/secrets/goreecloud-manager-beszel/credentials.json"
)
HEALTH_MAP = {
    0: "none",
    1: "starting",
    2: "healthy",
    3: "unhealthy",
}


class CollectorError(RuntimeError):
    """Sanitized collector failure with an artifact-safe state."""

    def __init__(self, state: str, message: str):
        super().__init__(message)
        self.state = state


def utc_now() -> datetime:
    return datetime.now(UTC)


def iso_utc(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def parse_timestamp(value: Any) -> datetime | None:
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


def number(value: Any, *, minimum: float = 0) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    result = float(value)
    return result if result >= minimum else None


def megabytes_to_gigabytes(value: Any) -> float | None:
    """Normalize Beszel container-memory values from MiB-equivalent MB to GiB."""

    parsed = number(value)
    return None if parsed is None else parsed / 1024


def integer(value: Any, *, minimum: int = 0) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        result = value
    elif isinstance(value, float) and value.is_integer():
        result = int(value)
    else:
        return None
    return result if result >= minimum else None


def load_credentials(path: Path) -> dict[str, str]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise CollectorError("error", "Beszel collector credential file is missing") from exc
    except (OSError, json.JSONDecodeError, TypeError) as exc:
        raise CollectorError("error", "Beszel collector credential file is invalid") from exc

    if not isinstance(payload, dict):
        raise CollectorError("error", "Beszel collector credential file is invalid")

    required = ("base_url", "email", "password")
    result: dict[str, str] = {}
    for key in required:
        value = payload.get(key)
        if not isinstance(value, str) or not value.strip():
            raise CollectorError("error", "Beszel collector credential file is incomplete")
        result[key] = value.strip()

    if not result["base_url"].startswith(("http://", "https://")):
        raise CollectorError("error", "Beszel collector base URL is invalid")

    return result


def request_json(
    base_url: str,
    path: str,
    *,
    token: str | None = None,
    method: str = "GET",
    payload: dict[str, Any] | None = None,
    params: dict[str, Any] | None = None,
    timeout: int = 10,
) -> tuple[int, Any]:
    url = base_url.rstrip("/") + path
    if params:
        url += "?" + urllib.parse.urlencode(params)

    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = token

    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    request = urllib.request.Request(url, data=data, headers=headers, method=method)

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read()
            try:
                parsed = json.loads(body)
            except json.JSONDecodeError as exc:
                raise CollectorError("error", "Beszel returned malformed JSON") from exc
            return response.status, parsed
    except urllib.error.HTTPError as exc:
        try:
            body = exc.read()
            parsed = json.loads(body) if body else None
        except (json.JSONDecodeError, OSError):
            parsed = None
        return exc.code, parsed
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise CollectorError("unavailable", "Beszel endpoint is unavailable") from exc


def collection_items(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, dict) or not isinstance(payload.get("items"), list):
        raise CollectorError("error", "Beszel collection response is malformed")

    items = payload["items"]
    if any(not isinstance(item, dict) for item in items):
        raise CollectorError("error", "Beszel collection response is malformed")
    return items


def require_ok(status: int, payload: Any, *, context: str) -> Any:
    if status != 200:
        raise CollectorError("error", f"Beszel {context} query failed")
    return payload


def normalize_health(value: Any) -> str:
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"none", "starting", "healthy", "unhealthy"}:
            return normalized
    parsed = integer(value)
    return HEALTH_MAP.get(parsed, "unknown") if parsed is not None else "unknown"


def normalize_temperatures(value: Any) -> dict[str, float]:
    if not isinstance(value, dict):
        return {}

    result: dict[str, float] = {}
    for key, raw in value.items():
        if not isinstance(key, str):
            continue
        parsed = number(raw, minimum=-273.15)
        if parsed is not None:
            result[key.strip()] = parsed
    return result


def normalize_bandwidth(value: Any) -> dict[str, int | None]:
    if not isinstance(value, list) or len(value) < 2:
        return {"sent_bytes": None, "recv_bytes": None}
    return {
        "sent_bytes": integer(value[0]),
        "recv_bytes": integer(value[1]),
    }


def newest_container_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Keep one Beszel container record per normalized name, preferring newest update."""

    selected: dict[str, dict[str, Any]] = {}
    for record in records:
        raw_name = record.get("name")
        if not isinstance(raw_name, str) or not raw_name.strip():
            continue

        key = raw_name.strip().casefold()
        current = selected.get(key)
        if current is None:
            selected[key] = record
            continue

        updated = parse_timestamp(record.get("updated"))
        current_updated = parse_timestamp(current.get("updated"))
        if updated is not None and (current_updated is None or updated > current_updated):
            selected[key] = record

    return list(selected.values())


def normalize_system(
    *,
    system: dict[str, Any],
    beszel_version: str,
    stats_record: dict[str, Any],
    details_record: dict[str, Any],
    container_records: list[dict[str, Any]],
    container_stats_record: dict[str, Any] | None,
) -> dict[str, Any]:
    name = system.get("name")
    status = system.get("status")
    updated = system.get("updated")
    info = system.get("info")
    if (
        not isinstance(name, str)
        or not name.strip()
        or not isinstance(status, str)
        or not status.strip()
        or parse_timestamp(updated) is None
        or not isinstance(info, dict)
    ):
        raise CollectorError("error", "Beszel system record is malformed")

    uptime_seconds = integer(info.get("u"))
    if uptime_seconds is None:
        raise CollectorError("error", "Beszel system uptime is malformed")

    stats = stats_record.get("stats")
    observed_at = stats_record.get("created") or stats_record.get("updated")
    if not isinstance(stats, dict) or parse_timestamp(observed_at) is None:
        raise CollectorError("error", "Beszel system statistics are malformed")

    details_fields = {
        "hostname": details_record.get("hostname", ""),
        "kernel": details_record.get("kernel", ""),
        "cpu_model": details_record.get("cpu", ""),
        "os_name": details_record.get("os_name", ""),
        "architecture": details_record.get("arch", ""),
    }
    if any(not isinstance(value, str) for value in details_fields.values()):
        raise CollectorError("error", "Beszel system details are malformed")

    podman = details_record.get("podman", False)
    if not isinstance(podman, bool):
        podman = False

    latest_container_stats: dict[str, dict[str, Any]] = {}
    if isinstance(container_stats_record, dict):
        raw_stats = container_stats_record.get("stats")
        if isinstance(raw_stats, list):
            for item in raw_stats:
                if not isinstance(item, dict):
                    continue
                stat_name = item.get("n")
                if isinstance(stat_name, str) and stat_name.strip():
                    latest_container_stats[stat_name.strip().casefold()] = item

    containers: list[dict[str, Any]] = []
    for record in newest_container_records(container_records):
        container_name = record.get("name")
        if not isinstance(container_name, str) or not container_name.strip():
            continue
        container_name = container_name.strip()
        dynamic = latest_container_stats.get(container_name.casefold(), {})
        state = record.get("status") or "Unknown"
        if not isinstance(state, str):
            state = "Unknown"

        containers.append(
            {
                "name": container_name,
                "state": state.strip() or "Unknown",
                "health": normalize_health(record.get("health")),
                "cpu_percent": number(dynamic.get("c"))
                if dynamic
                else number(record.get("cpu")),
                "memory_gb": megabytes_to_gigabytes(dynamic.get("m"))
                if dynamic
                else megabytes_to_gigabytes(record.get("memory")),
                "network": normalize_bandwidth(dynamic.get("b")) if dynamic else {
                    "sent_bytes": None,
                    "recv_bytes": None,
                },
            }
        )

    load_average = stats.get("la") if isinstance(stats.get("la"), list) else info.get("la", [])
    if not isinstance(load_average, list):
        load_average = []

    return {
        "source": {
            "name": name.strip(),
            "status": status.strip(),
            "updated_at": str(updated).strip(),
            "agent_version": str(info.get("v", "")).strip(),
            "beszel_version": beszel_version.strip(),
            "uptime_seconds": uptime_seconds,
        },
        "stats": {
            "observed_at": str(observed_at).strip(),
            "cpu_percent": number(stats.get("cpu")),
            "load_average": [value for value in (number(item) for item in load_average[:3]) if value is not None],
            "memory_total_gb": number(stats.get("m")),
            "memory_used_gb": number(stats.get("mu")),
            "memory_percent": number(stats.get("mp")),
            "swap_total_gb": number(stats.get("s")),
            "swap_used_gb": number(stats.get("su")),
            "disk_total_gb": number(stats.get("d")),
            "disk_used_gb": number(stats.get("du")),
            "disk_percent": number(stats.get("dp")),
            "network": normalize_bandwidth(stats.get("b")),
            "temperatures": normalize_temperatures(stats.get("t")),
        },
        "details": {
            "hostname": details_fields["hostname"].strip(),
            "kernel": details_fields["kernel"].strip(),
            "cores": integer(details_record.get("cores")),
            "threads": integer(details_record.get("threads")),
            "cpu_model": details_fields["cpu_model"].strip(),
            "os_name": details_fields["os_name"].strip(),
            "architecture": details_fields["architecture"].strip(),
            "memory_bytes": integer(details_record.get("memory")),
            "podman": podman,
        },
        "containers": sorted(containers, key=lambda item: item["name"].casefold()),
    }


def collect(base_url: str, email: str, password: str, *, timeout: int = 10) -> dict[str, Any]:
    status, auth = request_json(
        base_url,
        "/api/collections/users/auth-with-password",
        method="POST",
        payload={"identity": email, "password": password},
        timeout=timeout,
    )
    if status in {400, 401, 403}:
        raise CollectorError("auth_error", "Beszel rejected the delegated collector credential")
    if status != 200 or not isinstance(auth, dict):
        raise CollectorError("error", "Beszel authentication response is invalid")

    token = auth.get("token")
    record = auth.get("record")
    if not isinstance(token, str) or not token or not isinstance(record, dict):
        raise CollectorError("error", "Beszel authentication response is invalid")
    if record.get("role") != "readonly":
        raise CollectorError("auth_error", "Beszel delegated collector identity is not readonly")

    status, info = request_json(base_url, "/api/beszel/info", token=token, timeout=timeout)
    require_ok(status, info, context="version")
    if not isinstance(info, dict) or not isinstance(info.get("v"), str):
        raise CollectorError("error", "Beszel version response is malformed")
    beszel_version = info["v"]

    status, systems_payload = request_json(
        base_url,
        "/api/collections/systems/records",
        token=token,
        params={
            "page": 1,
            "perPage": 50,
            "fields": "id,name,status,updated,info",
        },
        timeout=timeout,
    )
    require_ok(status, systems_payload, context="systems")
    systems = collection_items(systems_payload)
    if len(systems) != 1:
        raise CollectorError("error", "Beszel delegated identity scope is not exactly one system")

    system = systems[0]
    system_id = system.get("id")
    if not isinstance(system_id, str) or not system_id.strip():
        raise CollectorError("error", "Beszel system record is missing its identifier")

    status, stats_payload = request_json(
        base_url,
        "/api/collections/system_stats/records",
        token=token,
        params={
            "page": 1,
            "perPage": 1,
            "filter": f"system='{system_id}'",
            "sort": "-created",
            "fields": "created,updated,stats",
        },
        timeout=timeout,
    )
    require_ok(status, stats_payload, context="system statistics")
    stats_items = collection_items(stats_payload)
    if not stats_items:
        raise CollectorError("error", "Beszel returned no system statistics")

    details_fields = "hostname,kernel,cores,threads,cpu,os,os_name,arch,memory,podman,updated"
    status, details_record = request_json(
        base_url,
        f"/api/collections/system_details/records/{urllib.parse.quote(system_id, safe='')}",
        token=token,
        params={"fields": details_fields},
        timeout=timeout,
    )
    require_ok(status, details_record, context="system details")
    if not isinstance(details_record, dict):
        raise CollectorError("error", "Beszel system-details response is malformed")

    status, containers_payload = request_json(
        base_url,
        "/api/collections/containers/records",
        token=token,
        params={
            "page": 1,
            "perPage": 200,
            "filter": f"system='{system_id}'",
            "fields": "name,status,health,cpu,memory,updated",
        },
        timeout=timeout,
    )
    require_ok(status, containers_payload, context="containers")
    container_records = collection_items(containers_payload)

    status, container_stats_payload = request_json(
        base_url,
        "/api/collections/container_stats/records",
        token=token,
        params={
            "page": 1,
            "perPage": 1,
            "filter": f"system='{system_id}'",
            "sort": "-created",
            "fields": "created,updated,stats",
        },
        timeout=timeout,
    )
    require_ok(status, container_stats_payload, context="container statistics")
    container_stats_items = collection_items(container_stats_payload)

    normalized = normalize_system(
        system=system,
        beszel_version=beszel_version,
        stats_record=stats_items[0],
        details_record=details_record,
        container_records=container_records,
        container_stats_record=container_stats_items[0] if container_stats_items else None,
    )

    token = ""
    auth = None
    return normalized


def load_previous_data(status_path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(status_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError, TypeError):
        return {}

    if not isinstance(payload, dict) or payload.get("schema_version") != SCHEMA_VERSION:
        return {}

    source = payload.get("source")
    stats = payload.get("stats")
    details = payload.get("details")
    containers = payload.get("containers")
    if not isinstance(source, dict) or not isinstance(stats, dict) or not isinstance(details, dict):
        return {}
    if not isinstance(containers, list):
        containers = []

    return {
        "source": source,
        "stats": stats,
        "details": details,
        "containers": containers,
    }


def atomic_write(status_path: Path, payload: dict[str, Any]) -> None:
    status_path.parent.mkdir(parents=True, exist_ok=True, mode=0o755)
    os.chmod(status_path.parent, 0o755)
    encoded = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    temporary_name: str | None = None

    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=status_path.parent,
            prefix=f".{status_path.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary:
            temporary_name = temporary.name
            temporary.write(encoded)
            temporary.flush()
            os.fsync(temporary.fileno())

        os.chmod(temporary_name, 0o644)
        os.replace(temporary_name, status_path)
        temporary_name = None
    finally:
        if temporary_name:
            try:
                Path(temporary_name).unlink()
            except FileNotFoundError:
                pass


def build_payload(
    *,
    now: datetime,
    collector_state: str,
    data: dict[str, Any] | None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": iso_utc(now),
        "collector": {
            "state": collector_state,
            "checked_at": iso_utc(now),
        },
        "source": None,
        "stats": None,
        "details": None,
        "containers": [],
    }
    if data:
        for key in ("source", "stats", "details", "containers"):
            if key in data:
                payload[key] = data[key]
    return payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--credentials", type=Path, default=DEFAULT_CREDENTIALS_PATH)
    parser.add_argument("--status-path", type=Path, default=DEFAULT_STATUS_PATH)
    parser.add_argument("--timeout", type=int, default=10)
    return parser


def main() -> int:
    args = build_parser().parse_args()

    if os.geteuid() != 0:
        print("ERROR: Beszel status collector must run as root.", file=sys.stderr)
        return 1

    now = utc_now()
    previous_data = load_previous_data(args.status_path)

    try:
        credentials = load_credentials(args.credentials)
        data = collect(
            credentials["base_url"],
            credentials["email"],
            credentials["password"],
            timeout=max(1, min(args.timeout, 60)),
        )
        payload = build_payload(now=now, collector_state="ok", data=data)
        atomic_write(args.status_path, payload)
        return 0
    except CollectorError as exc:
        payload = build_payload(
            now=now,
            collector_state=exc.state,
            data=previous_data or None,
        )
        try:
            atomic_write(args.status_path, payload)
        except OSError:
            print("ERROR: Beszel collector could not write the status artifact.", file=sys.stderr)
            return 1
        print(f"WARNING: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())