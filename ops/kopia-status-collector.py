#!/usr/bin/env python3
"""Produce GoreeCloud Manager's sanitized read-only Kopia status artifact.

This host-side helper is intended to run as root from the existing Kopia backup wrapper.
It may use the protected Kopia deployment to perform a read-only snapshot query, but it
writes only explicitly approved non-secret fields into the Manager integration-data path.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1
DEFAULT_STATUS_PATH = Path(
    "/srv/docker/appdata/goreecloud-manager/integrations/kopia/status.json"
)
DEFAULT_STACK_DIR = Path("/srv/docker/stacks/kopia")
DEFAULT_COMPOSE_FILE = "compose.yaml"
DEFAULT_SOURCE = "/source"
DEFAULT_SOURCE_HOST = "goreecloud-vps-01"
DEFAULT_SOURCE_LABEL = "GoreeCloud VPS protected data"


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


def nonnegative_int(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return None
    return value


def load_previous_snapshot(status_path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(status_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError, TypeError):
        return None

    if not isinstance(payload, dict) or payload.get("schema_version") != SCHEMA_VERSION:
        return None

    snapshot = payload.get("latest_snapshot")
    return snapshot if isinstance(snapshot, dict) else None


def normalize_snapshot(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ValueError("Kopia returned a non-object snapshot entry")

    snapshot_id = raw.get("id")
    if not isinstance(snapshot_id, str) or not snapshot_id.strip():
        raise ValueError("Kopia snapshot ID is missing")

    start_raw = raw.get("startTime")
    end_raw = raw.get("endTime")
    start_time = parse_timestamp(start_raw)
    end_time = parse_timestamp(end_raw)
    if start_time is None or end_time is None or end_time < start_time:
        raise ValueError("Kopia snapshot timestamps are invalid")

    root_entry = raw.get("rootEntry")
    summary = root_entry.get("summ") if isinstance(root_entry, dict) else None
    stats = raw.get("stats") if isinstance(raw.get("stats"), dict) else {}

    if not isinstance(summary, dict):
        summary = {}

    retention = raw.get("retentionReason", [])
    if not isinstance(retention, list):
        retention = []

    description = raw.get("description", "")
    if not isinstance(description, str):
        description = ""

    error_count = nonnegative_int(summary.get("numFailed"))
    if error_count is None:
        error_count = nonnegative_int(stats.get("errorCount"))

    size_bytes = nonnegative_int(summary.get("size"))
    if size_bytes is None:
        size_bytes = nonnegative_int(stats.get("totalSize"))

    return {
        "id": snapshot_id.strip(),
        "start_time": start_raw.strip(),
        "end_time": end_raw.strip(),
        "description": description.strip(),
        "size_bytes": size_bytes,
        "file_count": nonnegative_int(summary.get("files")),
        "directory_count": nonnegative_int(summary.get("dirs")),
        "error_count": error_count,
        "retention_reasons": [
            item.strip()
            for item in retention
            if isinstance(item, str) and item.strip()
        ],
    }


def query_latest_snapshot(
    *,
    stack_dir: Path,
    compose_file: str,
    source: str,
) -> dict[str, Any]:
    command = [
        "docker",
        "compose",
        "-f",
        compose_file,
        "run",
        "--rm",
        "kopia",
        "snapshot",
        "list",
        source,
        "--json",
        "--max-results=1",
    ]

    completed = subprocess.run(
        command,
        cwd=stack_dir,
        check=True,
        capture_output=True,
        text=True,
        timeout=180,
    )

    payload = json.loads(completed.stdout)
    if not isinstance(payload, list) or not payload:
        raise ValueError("Kopia returned no snapshots")

    return normalize_snapshot(payload[-1])


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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--attempt-state",
        required=True,
        choices=("success", "skipped", "failed", "unknown"),
    )
    parser.add_argument("--attempt-reason", required=True)
    parser.add_argument("--refresh-snapshot", action="store_true")
    parser.add_argument("--status-path", type=Path, default=DEFAULT_STATUS_PATH)
    parser.add_argument("--stack-dir", type=Path, default=DEFAULT_STACK_DIR)
    parser.add_argument("--compose-file", default=DEFAULT_COMPOSE_FILE)
    parser.add_argument("--source", default=DEFAULT_SOURCE)
    parser.add_argument("--source-host", default=DEFAULT_SOURCE_HOST)
    parser.add_argument("--source-label", default=DEFAULT_SOURCE_LABEL)
    return parser


def main() -> int:
    args = build_parser().parse_args()

    if os.geteuid() != 0:
        print("ERROR: Kopia status collector must run as root.", file=sys.stderr)
        return 1

    now = utc_now()
    latest_snapshot = load_previous_snapshot(args.status_path)
    repository_state = "not_attempted"
    repository_checked_at: str | None = None
    query_failed = False

    if args.refresh_snapshot:
        repository_checked_at = iso_utc(now)
        try:
            latest_snapshot = query_latest_snapshot(
                stack_dir=args.stack_dir,
                compose_file=args.compose_file,
                source=args.source,
            )
            repository_state = "ok"
        except (
            OSError,
            subprocess.SubprocessError,
            json.JSONDecodeError,
            ValueError,
        ):
            repository_state = "error"
            query_failed = True

    attempt_at = now
    if args.attempt_state == "success" and repository_state == "ok" and latest_snapshot:
        snapshot_end = parse_timestamp(latest_snapshot.get("end_time"))
        if snapshot_end is not None:
            attempt_at = snapshot_end

    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": iso_utc(now),
        "source": {
            "host": args.source_host,
            "label": args.source_label,
        },
        "repository_query": {
            "state": repository_state,
            "checked_at": repository_checked_at,
        },
        "latest_attempt": {
            "state": args.attempt_state,
            "at": iso_utc(attempt_at),
            "reason": args.attempt_reason,
        },
        "latest_snapshot": latest_snapshot,
    }

    atomic_write(args.status_path, payload)

    if query_failed:
        print(
            "WARNING: Kopia status artifact updated, but the read-only snapshot query failed.",
            file=sys.stderr,
        )
        return 2

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
