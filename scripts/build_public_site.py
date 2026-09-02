#!/usr/bin/env python3
from pathlib import Path
import hashlib
import json
import os
import shutil
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "website"
DIST = ROOT / "dist"
LOCK = json.loads((SOURCE / "glaze.lock.json").read_text(encoding="utf-8"))
PUBLIC_FILES = ("index.html", "404.html", "_headers", "robots.txt")
LOCAL_ASSETS = ("site.css", "site.js")

if LOCK.get("version") != "2.2.0" or LOCK.get("lifecycle") != "Stable":
    raise SystemExit("Glaze consumer lock must target 2.2.0 Stable")
if LOCK.get("stable_commit") != "6731098b28dd0393faa878c70d989a221d714a20":
    raise SystemExit("unexpected Glaze Stable promotion commit")

def git_blob_sha(data: bytes) -> str:
    prefix = b"blob " + str(len(data)).encode("ascii") + b"\0"
    return hashlib.sha1(prefix + data).hexdigest()

def require_file(path: Path) -> Path:
    if not path.is_file() or path.is_symlink():
        raise SystemExit(f"missing or unsafe public source: {path.relative_to(ROOT)}")
    return path

def read_glaze(name: str, expected_sha: str) -> bytes:
    source_root = os.environ.get("GLAZE_UI_SOURCE")
    if source_root:
        data = require_file(Path(source_root) / "css" / name).read_bytes()
    else:
        url = f"https://raw.githubusercontent.com/{LOCK['repository']}/{LOCK['tag']}/css/{name}"
        request = urllib.request.Request(url, headers={"User-Agent": "GoreeCloud-public-site-builder/1"})
        with urllib.request.urlopen(request, timeout=20) as response:
            data = response.read()
    actual_sha = git_blob_sha(data)
    if actual_sha != expected_sha:
        raise SystemExit(f"Glaze integrity mismatch for {name}: {actual_sha} != {expected_sha}")
    return data

if DIST.exists():
    shutil.rmtree(DIST)
(DIST / "assets").mkdir(parents=True)

for name in PUBLIC_FILES:
    shutil.copy2(require_file(SOURCE / name), DIST / name)
if (SOURCE / "sitemap.xml").exists():
    shutil.copy2(require_file(SOURCE / "sitemap.xml"), DIST / "sitemap.xml")
for name in LOCAL_ASSETS:
    shutil.copy2(require_file(SOURCE / name), DIST / "assets" / name)
for asset in sorted((SOURCE / "assets").iterdir()):
    if asset.is_symlink() or not asset.is_file():
        raise SystemExit(f"unsafe public asset: {asset.relative_to(ROOT)}")
    shutil.copy2(asset, DIST / "assets" / asset.name)
for name, expected_sha in LOCK["files"].items():
    (DIST / "assets" / name).write_bytes(read_glaze(name, expected_sha))

print(
    f"Built public site with Glaze UI {LOCK['version']} {LOCK['lifecycle']} "
    f"pinned to {LOCK['stable_commit']}"
)
