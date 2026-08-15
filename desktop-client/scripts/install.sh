#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TARGET="$HOME/.local/opt/goreecloud-manager"
PARENT="$(dirname "$TARGET")"

mkdir -p "$PARENT"
STAGE="$(mktemp -d "$PARENT/.goreecloud-manager.stage.XXXXXX")"
BACKUP="$(mktemp -d "$PARENT/.goreecloud-manager.rollback.XXXXXX")"
rmdir "$BACKUP"

cleanup() {
  status=$?
  trap - EXIT

  if [[ -d "$BACKUP" && ! -e "$TARGET" ]]; then
    mv "$BACKUP" "$TARGET" || true
  fi

  rm -rf "$STAGE"
  if [[ $status -eq 0 ]]; then
    rm -rf "$BACKUP"
  fi

  exit "$status"
}
trap cleanup EXIT

old_requirements_hash=""
if [[ -f "$TARGET/requirements.txt" ]]; then
  old_requirements_hash="$(sha256sum "$TARGET/requirements.txt" | awk '{print $1}')"
fi

tar --exclude='.venv' --exclude='__pycache__' --exclude='*.pyc' -C "$ROOT" -cf - . | tar -C "$STAGE" -xf -

new_requirements_hash="$(sha256sum "$STAGE/requirements.txt" | awk '{print $1}')"
if [[ -x "$TARGET/.venv/bin/python" && -n "$old_requirements_hash" && "$old_requirements_hash" == "$new_requirements_hash" ]]; then
  echo "Reusing existing Python environment (requirements unchanged)."
  cp -a "$TARGET/.venv" "$STAGE/.venv"
  "$STAGE/.venv/bin/python" -m pip check
else
  "$STAGE/scripts/setup.sh"
fi

"$STAGE/.venv/bin/python" -m compileall -q "$STAGE/goreecloud_manager"

if [[ -e "$TARGET" ]]; then
  mv "$TARGET" "$BACKUP"
fi

mv "$STAGE" "$TARGET"

if ! "$TARGET/scripts/install-desktop-entry.sh"; then
  rm -rf "$TARGET"
  if [[ -d "$BACKUP" ]]; then
    mv "$BACKUP" "$TARGET"
  fi
  echo "Installation failed while updating the desktop entry; the previous installation was restored." >&2
  exit 1
fi

printf '\nGoreeCloud Manager installed to:\n  %s\n\nLaunch it from your application menu or run:\n  %s/scripts/start.sh\n' "$TARGET" "$TARGET"
