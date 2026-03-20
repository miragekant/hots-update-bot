#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PYTHON="${ROOT}/.venv/bin/python"
MODE="${1:-both}"

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
