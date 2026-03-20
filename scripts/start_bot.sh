#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PYTHON="${ROOT}/.venv/bin/python"

echo "Evaluating bootstrap sync state"
if BOOTSTRAP_REASON="$("${PYTHON}" -m bot.bootstrap --format reason)"; then
  echo "${BOOTSTRAP_REASON}"
  "${ROOT}/scripts/update_cache.sh" both
else
  STATUS=$?
  if [[ "${STATUS}" -eq 1 ]]; then
    echo "${BOOTSTRAP_REASON}"
  else
    echo "failed to evaluate bootstrap sync state" >&2
    exit "${STATUS}"
  fi
fi

echo "Starting Discord bot"
exec "${PYTHON}" bot/run.py
