# News Updater Change Notes

## Scope Completed
- Added stdout logging with progress and summary in `news/update_news.py`.
- Added date-range controls with default 3-month window:
  - `--months` (default `3`)
  - `--from`
  - `--to`
  - `--limit`
  - `--verbose`
- Added runner script: `news/run_update_news.sh` (defaults to `--months 3`).
- Changed article file storage to chronological layout:
  - `news/articles/YYYY/MM/DD/{article_id}.json`
- Kept article JSON schema unchanged.
- Added/updated tests for discovery, date filtering, logging, and path layout.

## One-Time Migration
- Legacy flat files were migrated in prior run to chronological paths.
- Migration logic was removed afterward to keep runtime lean.
- Current implementation now only writes/uses chronological paths.

## Code Review Findings
- No blocking defects found in current implementation.
- Improvement applied: pagination now stops early when pages are older than the requested start date, reducing network effort for short windows.

## Validation
- Test suite: `7 passed` via `./.venv/bin/python -m pytest -q`.
- Live smoke run (network-enabled): updater runs with logs and stable summary output.

## Files Changed
- `news/update_news.py`
- `news/run_update_news.sh`
- `tests/test_update_news.py`
- `plans/news-crawler-logging-range-chronological-plan.md`
- `plans/news-updater-change-notes.md`
