#!/usr/bin/env python3
"""Create and validate consistent GoreeCloud Manager SQLite recovery points.

This helper intentionally uses SQLite's online backup API instead of copying a live database
file. It does not schedule backups, choose a production repository, or handle production
credentials. Restore writes only to a destination that does not already exist.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import tempfile
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def readonly_connection(path: Path) -> sqlite3.Connection:
    resolved = path.resolve(strict=True)
    return sqlite3.connect(f"file:{resolved}?mode=ro", uri=True, timeout=30)


def validate_database(path: Path) -> dict[str, int | str]:
    if not path.is_file():
        raise RuntimeError("SQLite database file does not exist")

    with readonly_connection(path) as connection:
        integrity = connection.execute("PRAGMA integrity_check").fetchone()
        if integrity != ("ok",):
            raise RuntimeError("SQLite integrity_check did not return ok")
        foreign_key_errors = connection.execute("PRAGMA foreign_key_check").fetchall()
        if foreign_key_errors:
            raise RuntimeError("SQLite foreign_key_check reported relationship errors")
        page_count = int(connection.execute("PRAGMA page_count").fetchone()[0])
        page_size = int(connection.execute("PRAGMA page_size").fetchone()[0])

    return {
        "integrity": "ok",
        "foreign_keys": "ok",
        "page_count": page_count,
        "page_size": page_size,
        "size_bytes": path.stat().st_size,
        "sha256": sha256(path),
    }


def publish_exclusive(temp_path: Path, destination: Path) -> None:
    """Publish one completed file without overwriting an existing recovery point."""

    if destination.exists():
        raise RuntimeError("Destination already exists; refusing to overwrite a recovery point")
    os.link(temp_path, destination)
    temp_path.unlink()


def clone_database(source: Path, destination: Path, operation: str) -> dict[str, int | str]:
    source = source.resolve(strict=True)
    destination = destination.resolve(strict=False)

    if source == destination:
        raise RuntimeError("Source and destination must be different files")
    if destination.exists():
        raise RuntimeError("Destination already exists; refusing to overwrite it")
    destination.parent.mkdir(parents=True, exist_ok=True)

    validate_database(source)

    fd, raw_temp_path = tempfile.mkstemp(
        prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent
    )
    os.close(fd)
    temp_path = Path(raw_temp_path)

    try:
        with readonly_connection(source) as source_connection:
            with sqlite3.connect(temp_path, timeout=30) as destination_connection:
                source_connection.backup(destination_connection)
                destination_connection.commit()

        os.chmod(temp_path, 0o600)
        metadata = validate_database(temp_path)
        with temp_path.open("rb+") as handle:
            handle.flush()
            os.fsync(handle.fileno())
        publish_exclusive(temp_path, destination)
        metadata["operation"] = operation
        return metadata
    finally:
        temp_path.unlink(missing_ok=True)


def backup(source: Path, destination: Path) -> dict[str, int | str]:
    return clone_database(source, destination, "backup")


def restore(source: Path, destination: Path) -> dict[str, int | str]:
    return clone_database(source, destination, "restore")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    for command in ("backup", "restore"):
        command_parser = subparsers.add_parser(command)
        command_parser.add_argument("source", type=Path)
        command_parser.add_argument("destination", type=Path)

    verify_parser = subparsers.add_parser("verify")
    verify_parser.add_argument("database", type=Path)

    args = parser.parse_args()
    if args.command == "backup":
        result = backup(args.source, args.destination)
    elif args.command == "restore":
        result = restore(args.source, args.destination)
    else:
        result = validate_database(args.database)
        result["operation"] = "verify"

    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
