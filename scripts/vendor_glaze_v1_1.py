#!/usr/bin/env python3
"""Vendor the exact locked GLAZE UI V1.1 Stable web source into Manager."""

from __future__ import annotations

import argparse
import hashlib
import json
import posixpath
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOCK_PATH = ROOT / "core/static/core/glaze.lock.json"
DESTINATION = ROOT / "core/static/core/glaze"
EXPECTED_RELEASE = "15cc76d2bcd4065552dc31c77145b63f34d9e7b2"
IMPORT_RE = re.compile(r"@import\s+([^;]+);", re.IGNORECASE)


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


def parse_import(statement: str, source_path: str) -> str:
    spec = statement.strip()
    match = re.match(r"""url\(\s*(['"])(.*?)\1\s*\)""", spec, re.IGNORECASE)
    if match is None:
        match = re.match(r"""(['"])(.*?)\1""", spec)
    if match is None:
        raise SystemExit(f"unsupported CSS @import syntax in {source_path}: {statement!r}")
    target = match.group(2).strip()
    if not target:
        raise SystemExit(f"empty CSS @import target in {source_path}")
    if "://" in target or target.startswith("//"):
        raise SystemExit(f"remote CSS @import is forbidden in {source_path}: {target}")
    if target.startswith("/"):
        raise SystemExit(f"root-absolute CSS @import is forbidden in {source_path}: {target}")
    if "?" in target or "#" in target:
        raise SystemExit(f"query/fragment CSS @import is forbidden in {source_path}: {target}")
    return target


def validate_import_closure(entrypoint: str, files: dict[str, object], source: Path) -> None:
    locked_paths = set(files)
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(upstream_path: str) -> None:
        if upstream_path in visiting:
            raise SystemExit(f"cyclic CSS @import detected at {upstream_path}")
        if upstream_path in visited:
            return
        if upstream_path not in locked_paths:
            raise SystemExit(f"missing CSS import target in locked Glaze graph: {upstream_path}")
        source_path = source / upstream_path
        if source_path.is_symlink() or not source_path.is_file():
            raise SystemExit(f"missing or unsafe Glaze source: {upstream_path}")
        try:
            css = source_path.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            raise SystemExit(f"non-UTF-8 Glaze CSS source: {upstream_path}") from exc

        visiting.add(upstream_path)
        for statement in IMPORT_RE.findall(css):
            target = parse_import(statement, upstream_path)
            resolved = posixpath.normpath(
                posixpath.join(posixpath.dirname(upstream_path), target)
            )
            if resolved.startswith("../") or resolved == ".." or not resolved.startswith("css/"):
                raise SystemExit(
                    f"CSS @import escapes the locked css/ graph in {upstream_path}: {target}"
                )
            visit(resolved)
        visiting.remove(upstream_path)
        visited.add(upstream_path)

    visit(entrypoint)


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

    # Validate the entire immutable import graph before mutating the destination.
    # This deliberately rejects the known v1.1.0 stale candidate import until a
    # corrected immutable Stable release is published and Manager is re-pinned.
    entrypoint = lock["entrypoint"]
    assert isinstance(entrypoint, str)
    validate_import_closure(entrypoint, files, source)

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

    reset_destination()

    for upstream_path in files:
        assert isinstance(upstream_path, str)
        source_path = source / upstream_path
        (DESTINATION / Path(upstream_path).name).write_bytes(source_path.read_bytes())

    expected_names = {Path(path).name for path in files}
    actual_names = {
        path.name
        for path in DESTINATION.iterdir()
        if path.is_file() and not path.is_symlink()
    }
    if actual_names != expected_names:
        raise SystemExit("vendored Glaze filename set mismatch")

    for upstream_path, expected_sha in files.items():
        destination_path = DESTINATION / Path(upstream_path).name
        if destination_path.is_symlink() or not destination_path.is_file():
            raise SystemExit(f"missing or unsafe vendored Glaze source: {upstream_path}")
        if blob_sha(destination_path.read_bytes()) != expected_sha:
            raise SystemExit(f"vendored Glaze integrity mismatch: {upstream_path}")

    print(f"Vendored {len(files)} import-closed locked GLAZE UI V1.1 files from {EXPECTED_RELEASE}")


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
