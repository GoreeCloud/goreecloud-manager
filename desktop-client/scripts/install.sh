#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TARGET="$HOME/.local/opt/goreecloud-manager"
TMPDIR="$(mktemp -d)"
trap 'rm -rf "$TMPDIR"' EXIT

mkdir -p "$(dirname "$TARGET")"

old_requirements_hash=""
if [[ -f "$TARGET/requirements.txt" ]]; then
  old_requirements_hash="$(sha256sum "$TARGET/requirements.txt" | awk '{print $1}')"
fi

if [[ -d "$TARGET/.venv" ]]; then
  mv "$TARGET/.venv" "$TMPDIR/.venv"
fi

rm -rf "$TARGET"
mkdir -p "$TARGET"
tar --exclude='.venv' --exclude='__pycache__' --exclude='*.pyc' -C "$ROOT" -cf - . | tar -C "$TARGET" -xf -

if [[ -d "$TMPDIR/.venv" ]]; then
  mv "$TMPDIR/.venv" "$TARGET/.venv"
fi

new_requirements_hash="$(sha256sum "$TARGET/requirements.txt" | awk '{print $1}')"
if [[ -x "$TARGET/.venv/bin/python" && -n "$old_requirements_hash" && "$old_requirements_hash" == "$new_requirements_hash" ]]; then
  echo "Reusing existing Python environment (requirements unchanged)."
else
  "$TARGET/scripts/setup.sh"
fi

"$TARGET/scripts/install-desktop-entry.sh"

printf '\nGoreeCloud Manager installed to:\n  %s\n\nLaunch it from your application menu or run:\n  %s/scripts/start.sh\n' "$TARGET" "$TARGET"
