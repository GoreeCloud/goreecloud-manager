#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if ! command -v python3 >/dev/null 2>&1; then
  echo "Python 3 is required but was not found." >&2
  exit 1
fi

if [[ ! -x .venv/bin/python ]]; then
  echo "Creating Python virtual environment..."
  python3 -m venv .venv
fi

. .venv/bin/activate
export PIP_DISABLE_PIP_VERSION_CHECK=1
python -m pip install -r requirements.txt
python -m pip check
printf '\nSetup complete. Run: ./scripts/start.sh\n'
