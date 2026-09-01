#!/usr/bin/env python3
"""Collect license/copyright material for the exact bundled desktop runtime.

Run this from the same Python environment used by PyInstaller. The collector
fails closed if an expected bundled distribution is unavailable or exposes no
license/copyright material through its installed wheel metadata.
"""

from __future__ import annotations

import argparse
import importlib.metadata as metadata
import re
import shutil
import sys
from pathlib import Path

EXPECTED_DISTRIBUTIONS = (
    "PySide6",
    "PySide6_Addons",
    "PySide6_Essentials",
    "shiboken6",
    "psutil",
    "PyYAML",
    "pyinstaller",
)
NOTICE_PREFIXES = ("license", "copying", "notice", "copyright", "authors")
SAFE_COMPONENT = re.compile(r"[^A-Za-z0-9._+-]+")


def _is_notice_file(relative: Path) -> bool:
    name = relative.name.casefold()
    parts = {part.casefold() for part in relative.parts}
    return "licenses" in parts or name.startswith(NOTICE_PREFIXES)


def _component_dir(name: str, version: str) -> str:
    return SAFE_COMPONENT.sub("-", f"{name}-{version}").strip("-")


def _safe_relative(relative: Path) -> Path:
    if relative.is_absolute() or ".." in relative.parts:
        raise RuntimeError("bundled distribution license path escaped its package metadata boundary")
    return relative


def collect_distribution(name: str, destination: Path) -> tuple[str, str, int]:
    try:
        dist = metadata.distribution(name)
    except metadata.PackageNotFoundError as exc:
        raise RuntimeError(f"required bundled distribution is unavailable: {name}") from exc

    canonical_name = str(dist.metadata.get("Name") or name)
    version = str(dist.version)
    component = destination / _component_dir(canonical_name, version)
    files = list(dist.files or ())
    notice_files = [relative for relative in files if _is_notice_file(Path(str(relative)))]
    copied = 0

    for relative in notice_files:
        relative_path = _safe_relative(Path(str(relative)))
        source = Path(dist.locate_file(relative))
        if not source.is_file():
            continue
        target = component / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        copied += 1

    if copied == 0:
        raise RuntimeError(
            f"required bundled distribution exposes no installed license material: {canonical_name} {version}"
        )
    return canonical_name, version, copied


def collect_python_runtime(destination: Path) -> Path:
    major, minor = sys.version_info[:2]
    doc_root = Path("/usr/share/doc")
    candidates = [
        doc_root / f"python{major}.{minor}" / "copyright",
        doc_root / f"python{major}.{minor}-minimal" / "copyright",
        doc_root / f"libpython{major}.{minor}-stdlib" / "copyright",
        doc_root / "python3" / "copyright",
    ]
    for name in ("LICENSE", "LICENSE.txt", "COPYING", "COPYING.txt"):
        candidates.append(Path(sys.base_prefix) / name)

    for source in candidates:
        if source.is_file() and source.stat().st_size > 0:
            target_dir = destination / "CPython-runtime"
            target_dir.mkdir(parents=True, exist_ok=True)
            target = target_dir / source.name
            shutil.copy2(source, target)
            return target
    raise RuntimeError("packaged Python runtime license/copyright material was not found")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination")
    args = parser.parse_args()

    destination = Path(args.destination).resolve()
    destination.mkdir(parents=True, exist_ok=True)
    records: list[tuple[str, str, int]] = []
    try:
        for name in EXPECTED_DISTRIBUTIONS:
            records.append(collect_distribution(name, destination))
        python_notice = collect_python_runtime(destination)
    except (OSError, RuntimeError) as exc:
        print(f"license material collection error: {exc}", file=sys.stderr)
        return 2

    manifest = destination / "MANIFEST.txt"
    lines = ["Bundled Python distribution license material:"]
    lines.extend(f"- {name} {version}: {count} file(s)" for name, version, count in records)
    lines.extend(("", f"Packaged Python runtime notice: {python_notice.relative_to(destination)}", ""))
    manifest.write_text("\n".join(lines), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
