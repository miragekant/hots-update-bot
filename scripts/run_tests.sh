#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PYTHON="${ROOT}/.venv/bin/python"
VENV_DIR="${ROOT}/.venv"

if [[ ! -x "${PYTHON}" ]]; then
  echo "Python virtualenv not found at ${PYTHON}"
  echo "Creating virtualenv and installing dependencies"

  PYTHON3_BIN="${PYTHON3_BIN:-$(command -v python3 || true)}"
  if [[ -z "${PYTHON3_BIN}" ]]; then
    echo "python3 is required to create ${VENV_DIR}" >&2
    exit 127
  fi

  "${PYTHON3_BIN}" -m venv "${VENV_DIR}"
  "${PYTHON}" -m pip install --upgrade pip
  "${PYTHON}" -m pip install -r "${ROOT}/requirements.txt"
fi

echo "Running test suite"
echo "+ ${PYTHON} -m pytest -q $*"
exec "${PYTHON}" -m pytest -q "$@"
