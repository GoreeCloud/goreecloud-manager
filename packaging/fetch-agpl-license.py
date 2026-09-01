#!/usr/bin/env python3
"""Fetch and verify the canonical AGPLv3 legal text used in binary packages."""

from __future__ import annotations

import argparse
import hashlib
import sys
import urllib.error
import urllib.request
from pathlib import Path

CANONICAL_URL = (
    "https://raw.githubusercontent.com/GoreeCloud/goreecloud-tasks/"
    "9d4f2bca2f754ab1eca7b518dd062b330689b969/LICENSE"
)
EXPECTED_GIT_BLOB_SHA1 = "be3f7b28e564e7dd05eaf59d64adba1a4065ac0e"
MAX_BYTES = 128 * 1024


def git_blob_sha1(payload: bytes) -> str:
    header = f"blob {len(payload)}\0".encode("ascii")
    return hashlib.sha1(header + payload, usedforsecurity=False).hexdigest()


def fetch() -> bytes:
    request = urllib.request.Request(CANONICAL_URL, headers={"User-Agent": "GoreeCloud-Manager-License-Build/1"})
    with urllib.request.urlopen(request, timeout=15) as response:
        payload = response.read(MAX_BYTES + 1)
    if len(payload) > MAX_BYTES:
        raise ValueError("canonical AGPL text exceeded the bounded download size")
    if git_blob_sha1(payload) != EXPECTED_GIT_BLOB_SHA1:
        raise ValueError("canonical AGPL text did not match the pinned Git blob identity")
    if b"GNU AFFERO GENERAL PUBLIC LICENSE" not in payload or b"Version 3, 19 November 2007" not in payload:
        raise ValueError("canonical AGPL text is missing expected legal-text markers")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination")
    args = parser.parse_args()
    try:
        payload = fetch()
        destination = Path(args.destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(payload)
    except (OSError, ValueError, urllib.error.URLError) as exc:
        print(f"AGPL license retrieval error: {type(exc).__name__}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
