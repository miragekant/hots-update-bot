#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PYTHON="${ROOT}/.venv/bin/python"
VENV_DIR="${ROOT}/.venv"
MODE="${1:-both}"

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

if [[ $# -gt 0 ]]; then
  shift
fi

run_news() {
  echo "Running news cache update"
  echo "+ ${PYTHON} news/update_news.py $*"
  "${PYTHON}" news/update_news.py "$@"
}

run_heroes() {
  echo "Running HeroesProfile cache update"
  echo "+ ${PYTHON} heroesprofile/update_data.py $*"
  "${PYTHON}" heroesprofile/update_data.py "$@"
}

case "${MODE}" in
  both)
    if [[ $# -gt 0 ]]; then
      echo "extra arguments are only supported for 'news' or 'heroes' mode" >&2
      exit 2
    fi
    run_news
    run_heroes
    ;;
  news)
    run_news "$@"
    ;;
  heroes)
    run_heroes "$@"
    ;;
  *)
    echo "usage: ./scripts/update_cache.sh [news|heroes|both] [updater args]" >&2
    exit 2
    ;;
esac
