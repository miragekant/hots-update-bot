#!/usr/bin/env bash
set -euo pipefail

# Default sync window: last 3 months.
./.venv/bin/python news/update_news.py --months 3 "$@"
