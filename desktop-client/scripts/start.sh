#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ ! -x .venv/bin/python ]]; then
  echo "First launch: preparing GoreeCloud Manager..."
  "$ROOT/scripts/setup.sh"
fi

exec .venv/bin/python -m goreecloud_manager
