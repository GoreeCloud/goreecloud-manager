#!/usr/bin/env python3
"""Validate the self-contained Glaze UI reference package without third-party dependencies."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOKENS = ROOT / "tokens" / "glaze.tokens.json"
REQUIRED = [
    ROOT / "VERSION",
    ROOT / "README.md",
    ROOT / "CONFORMANCE.md",
    ROOT / "COMPONENTS.md",
    ROOT / "css" / "glaze.css",
    ROOT / "css" / "glaze.accessibility.css",
    ROOT / "reference" / "index.html",
    TOKENS,
]


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def main() -> None:
    for path in REQUIRED:
        require(path.is_file(), f"missing required Glaze UI file: {path.relative_to(ROOT)}")

    version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    data = json.loads(TOKENS.read_text(encoding="utf-8"))
    require(data["meta"]["version"] == version, "VERSION and token version differ")

    for theme in ("light", "dark"):
        colors = data["color"][theme]
        for name in ("canvas", "surface", "surfaceStrong", "text", "muted", "accent", "accentSecondary", "success", "warning", "danger"):
            require(name in colors, f"missing {theme} semantic color: {name}")

    require(data["target"]["minimum"] >= 44, "minimum target size must remain at least 44px")
    require(data["motion"]["fast"] < data["motion"]["standard"] < data["motion"]["emphasized"], "motion durations are not ordered")
    require(data["breakpoint"]["mediumMin"] == data["breakpoint"]["compactMax"] + 1, "compact/medium breakpoint gap")
    require(data["breakpoint"]["expandedMin"] > data["breakpoint"]["mediumMin"], "expanded breakpoint invalid")
    require(data["breakpoint"]["wideMin"] > data["breakpoint"]["expandedMin"], "wide breakpoint invalid")

    css = (ROOT / "css" / "glaze.css").read_text(encoding="utf-8")
    accessibility = (ROOT / "css" / "glaze.accessibility.css").read_text(encoding="utf-8")
    reference = (ROOT / "reference" / "index.html").read_text(encoding="utf-8")

    for token in ("--glaze-canvas", "--glaze-surface", "--glaze-accent", "--glaze-radius-xl", "--glaze-motion-standard", "--glaze-target-min"):
        require(token in css, f"canonical CSS missing {token}")

    for contract in ("prefers-reduced-motion", "prefers-contrast", "forced-colors", "@supports not"):
        require(contract in accessibility, f"accessibility CSS missing {contract}")

    require("fonts.googleapis" not in reference and "fonts.gstatic" not in reference, "reference page must not depend on remote Google Fonts")
    require("http://" not in reference and "https://" not in reference, "reference page must remain dependency-free")
    require("Glaze UI 1.0" in reference, "reference page identity missing")

    print(f"Glaze UI {version} reference package validated")


if __name__ == "__main__":
    main()
