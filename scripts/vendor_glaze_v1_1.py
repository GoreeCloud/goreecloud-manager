#!/usr/bin/env python3
"""Vendor the exact locked GLAZE UI V1.1 Stable web source into Manager."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOCK_PATH = ROOT / "core/static/core/glaze.lock.json"
DESTINATION = ROOT / "core/static/core/glaze"
EXPECTED_RELEASE = "15cc76d2bcd4065552dc31c77145b63f34d9e7b2"


def blob_sha(data: bytes) -> str:
    prefix = b"blob " + str(len(data)).encode("ascii") + b"\0"
    return hashlib.sha1(prefix + data, usedforsecurity=False).hexdigest()


def load_lock() -> dict[str, object]:
    lock = json.loads(LOCK_PATH.read_text(encoding="utf-8"))
    if lock.get("schema") != "goreecloud.glaze-ui.web-source-manifest.v1":
        raise SystemExit("unexpected Glaze lock schema")
    if lock.get("product") != "GLAZE UI V1.1" or lock.get("version") != "1.1.0":
        raise SystemExit("Glaze lock is not V1.1 / 1.1.0")
    if lock.get("tag") != "v1.1.0" or lock.get("release_commit") != EXPECTED_RELEASE:
        raise SystemExit("Glaze lock release identity mismatch")
    if lock.get("entrypoint") != "css/glaze-v1.1.0.css":
        raise SystemExit("Glaze lock entrypoint mismatch")
    if lock.get("runtime_network_dependency_required") is not False:
        raise SystemExit("Manager must not require a runtime Glaze network dependency")
    files = lock.get("files")
    if not isinstance(files, dict) or len(files) != 13:
        raise SystemExit("Glaze lock must contain exactly 13 files")
    return lock


def reset_destination() -> None:
    if DESTINATION.is_symlink():
        DESTINATION.unlink()
    elif DESTINATION.exists() and not DESTINATION.is_dir():
        DESTINATION.unlink()
    DESTINATION.mkdir(parents=True, exist_ok=True)
    for child in DESTINATION.iterdir():
        if child.is_dir() and not child.is_symlink():
            shutil.rmtree(child)
        else:
            child.unlink()


def vendor(source: Path) -> None:
    lock = load_lock()
    files = lock["files"]
    assert isinstance(files, dict)
    reset_destination()

    for upstream_path, expected_sha in files.items():
        if not isinstance(upstream_path, str) or not isinstance(expected_sha, str):
            raise SystemExit("invalid Glaze lock entry")
        source_path = source / upstream_path
        if source_path.is_symlink() or not source_path.is_file():
            raise SystemExit(f"missing or unsafe Glaze source: {upstream_path}")
        data = source_path.read_bytes()
        actual_sha = blob_sha(data)
        if actual_sha != expected_sha:
            raise SystemExit(f"Glaze source integrity mismatch: {upstream_path}")
        (DESTINATION / Path(upstream_path).name).write_bytes(data)

    expected_names = {Path(path).name for path in files}
    actual_names = {path.name for path in DESTINATION.iterdir() if path.is_file() and not path.is_symlink()}
    if actual_names != expected_names:
        raise SystemExit("vendored Glaze filename set mismatch")

    for upstream_path, expected_sha in files.items():
        destination_path = DESTINATION / Path(upstream_path).name
        if destination_path.is_symlink() or not destination_path.is_file():
            raise SystemExit(f"missing or unsafe vendored Glaze source: {upstream_path}")
        if blob_sha(destination_path.read_bytes()) != expected_sha:
            raise SystemExit(f"vendored Glaze integrity mismatch: {upstream_path}")

    print(f"Vendored {len(files)} locked GLAZE UI V1.1 files from {EXPECTED_RELEASE}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, type=Path)
    args = parser.parse_args()
    source = args.source.resolve()
    if not source.is_dir():
        raise SystemExit("Glaze source directory does not exist")
    vendor(source)


if __name__ == "__main__":
    main()
