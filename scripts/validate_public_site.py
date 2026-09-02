#!/usr/bin/env python3
from pathlib import Path
from html.parser import HTMLParser
import argparse
import hashlib
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "website"
DIST = ROOT / "dist"
PRODUCT = ROOT.name.lower()
parser = argparse.ArgumentParser()
parser.add_argument("--dist", action="store_true")
args = parser.parse_args()
BASE = DIST if args.dist else SOURCE
errors = []

def check(condition: bool, message: str) -> None:
    if not condition:
        errors.append(message)

def blob_sha(path: Path) -> str:
    data = path.read_bytes()
    prefix = b"blob " + str(len(data)).encode("ascii") + b"\0"
    return hashlib.sha1(prefix + data).hexdigest()

class PublicHtmlAudit(HTMLParser):
    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        src = values.get("src", "")
        if src.startswith(("http://", "https://", "//")):
            errors.append(f"remote runtime source is forbidden: {src}")
        if tag == "link":
            href = values.get("href", "")
            rel = values.get("rel", "")
            if href.startswith(("http://", "https://", "//")) and "canonical" not in rel.split():
                errors.append(f"remote runtime link is forbidden: {href}")
        if tag == "a":
            href = values.get("href", "")
            if href.startswith("http://"):
                errors.append(f"external navigation must use HTTPS: {href}")

lock = json.loads((SOURCE / "glaze.lock.json").read_text(encoding="utf-8"))
check(lock.get("version") == "2.2.0", "Glaze version must be 2.2.0")
check(lock.get("lifecycle") == "Stable", "Glaze lifecycle must be Stable")
check(lock.get("stable_commit") == "6731098b28dd0393faa878c70d989a221d714a20", "Glaze Stable commit must be pinned")
check(lock.get("tag") == "v2.2.0", "Glaze Stable tag must be pinned")

html = (BASE / "index.html").read_text(encoding="utf-8")
css = (BASE / "assets" / "site.css" if args.dist else SOURCE / "site.css").read_text(encoding="utf-8")
js = (BASE / "assets" / "site.js" if args.dist else SOURCE / "site.js").read_text(encoding="utf-8")
PublicHtmlAudit().feed(html)

check('data-glaze-version="2.2.0"' in html, "missing Glaze 2.2.0 document marker")
check('name="goreecloud-glaze-ui" content="2.2.0"' in html, "missing Glaze 2.2.0 meta marker")
check('/assets/glaze-2.2.0.css' in html, "Stable Glaze stylesheet entrypoint not linked")
check("prefers-reduced-motion:reduce" in css, "reduced-motion fallback missing")
check("forced-colors:active" in css, "forced-colors fallback missing")
check("prefers-contrast:more" in css, "increased-contrast fallback missing")
check("data-reduce-transparency" in css, "reduced-transparency fallback missing")
check("min-height:48px" in css, "48px interaction floor missing")
check("localStorage" in js and all(choice in js for choice in ("system", "light", "dark")), "appearance modes missing")
check("fonts.googleapis" not in html + css, "remote fonts are forbidden")
check("googletagmanager" not in html.lower(), "analytics/tracker runtime is forbidden")
check("segment.com" not in html.lower(), "analytics/tracker runtime is forbidden")
headers = (BASE / "_headers").read_text(encoding="utf-8")
check("Content-Security-Policy:" in headers, "Content Security Policy missing")
check("connect-src 'none'" in headers, "public website must not make browser network API connections")
check("Referrer-Policy: no-referrer" in headers, "strict referrer policy missing")

if "mesh" in PRODUCT:
    mark = SOURCE / "assets" / "goreecloud-mesh-mark.svg"
    check(mark.exists(), "Mesh mark missing")
    if mark.exists():
        check(blob_sha(mark) == "0b2c6881668ce319081390b217f6d59b4298dd4d", "Mesh mark diverged from approved Weave blob")
    check("authority_transfer = false" in html, "Mesh authority-transfer invariant missing")
    check('rel="canonical" href="https://mesh.goreecloud.com/"' in html, "Mesh intended canonical URL missing")
    check("Production acceptance stays explicit" in html, "Mesh production truth boundary missing")
else:
    mark = SOURCE / "assets" / "manager-mark.svg"
    check(mark.exists(), "Manager mark missing")
    if mark.exists():
        check(blob_sha(mark) == "81d5d6659bf22ee61a1be46fce816031b835f967", "Manager mark diverged from approved product blob")
    check("noindex,nofollow,noarchive" in html, "Manager must remain noindex before public hostname approval")
    check("manager.goreecloud.com" not in html, "private Manager application hostname must not be advertised by public site")
    check("Disallow: /" in (BASE / "robots.txt").read_text(encoding="utf-8"), "Manager robots must block indexing before public hostname approval")
    check("Conceptual · no live data" in html, "Manager conceptual graphic must be labeled non-live")

if args.dist:
    for name, expected_sha in lock["files"].items():
        path = DIST / "assets" / name
        check(path.exists(), f"missing built Glaze asset: {name}")
        if path.exists():
            check(blob_sha(path) == expected_sha, f"Glaze asset integrity mismatch: {name}")
    check((DIST / "_headers").exists(), "built security headers missing")

if errors:
    print("Public website validation failed:", file=sys.stderr)
    for error in errors:
        print(f" - {error}", file=sys.stderr)
    raise SystemExit(1)
print(f"Public website validation passed ({'dist' if args.dist else 'source'})")
