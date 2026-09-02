#!/usr/bin/env python3
"""Collect licensing evidence for the exact bundled desktop runtime.

Run this from the same Python environment used by PyInstaller. The collector
fails closed when an expected bundled distribution is unavailable or exposes
neither installed license/copyright files nor a declared license in its
installed wheel metadata. Metadata-only alias wheels are preserved as explicit
auditable records rather than being treated as though they shipped a license
file that does not exist.
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


def _metadata_values(dist: metadata.Distribution, header: str) -> list[str]:
    values = dist.metadata.get_all(header) or ()
    return [str(value).strip() for value in values if str(value).strip()]


def _declared_license_metadata(dist: metadata.Distribution) -> list[tuple[str, str]]:
    declarations: list[tuple[str, str]] = []
    for header in ("License-Expression", "License"):
        for value in _metadata_values(dist, header):
            if value.casefold() not in {"unknown", "n/a", "none"}:
                declarations.append((header, value))
    for value in _metadata_values(dist, "Classifier"):
        if value.startswith("License ::"):
            declarations.append(("Classifier", value))
    return declarations


def _write_metadata_license_record(
    dist: metadata.Distribution,
    component: Path,
    canonical_name: str,
    version: str,
) -> Path:
    declarations = _declared_license_metadata(dist)
    if not declarations:
        raise RuntimeError(
            "required bundled distribution exposes neither installed license files nor declared "
            f"license metadata: {canonical_name} {version}"
        )

    component.mkdir(parents=True, exist_ok=True)
    record = component / "PACKAGE-LICENSE-METADATA.txt"
    lines = [
        "Installed distribution licensing metadata",
        f"Name: {canonical_name}",
        f"Version: {version}",
        "Dedicated installed license/copyright files detected: none",
        "",
        "Declared licensing fields from installed wheel metadata:",
    ]
    lines.extend(f"{header}: {value}" for header, value in declarations)
    lines.extend(
        (
            "",
            "This record preserves the licensing declaration supplied by the installed distribution.",
            "It does not claim that the wheel contained a standalone license file.",
            "",
        )
    )
    record.write_text("\n".join(lines), encoding="utf-8")
    return record


def collect_distribution(name: str, destination: Path) -> tuple[str, str, int, str]:
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
        _write_metadata_license_record(dist, component, canonical_name, version)
        return canonical_name, version, 1, "metadata record"
    return canonical_name, version, copied, "installed notice file(s)"


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
    records: list[tuple[str, str, int, str]] = []
    try:
        for name in EXPECTED_DISTRIBUTIONS:
            records.append(collect_distribution(name, destination))
        python_notice = collect_python_runtime(destination)
    except (OSError, RuntimeError) as exc:
        print(f"license material collection error: {exc}", file=sys.stderr)
        return 2

    manifest = destination / "MANIFEST.txt"
    lines = ["Bundled Python distribution licensing evidence:"]
    lines.extend(f"- {name} {version}: {count} {evidence}" for name, version, count, evidence in records)
    lines.extend(("", f"Packaged Python runtime notice: {python_notice.relative_to(destination)}", ""))
    manifest.write_text("\n".join(lines), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
