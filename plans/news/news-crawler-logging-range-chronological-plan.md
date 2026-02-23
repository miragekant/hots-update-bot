# Update Plan: Logging, Time-Range Sync, and Chronological Storage

## Summary
Enhance `news/update_news.py` to:
1. add useful stdout logging with progress counters,
2. support range-based updates via CLI (`--months/--from/--to`) with default `--months 3`,
3. store article JSON files in chronological folders: `news/articles/YYYY/MM/DD/{id}.json`,
4. keep article JSON schema unchanged,
5. add minimum tests for new behavior.

Chosen decisions:
- Logging: `INFO` + progress counters (with optional debug support).
- Time range: CLI options, default `--months 3`.
- Range scope: only fetch articles inside the specified range.
- Storage layout: `news/articles/YYYY/MM/DD/{id}.json`.
- Add runner script to execute updater with default `--months 3`.

## Implementation Changes

## 1. Logging
Update `news/update_news.py`:
- Add `logging` setup (`StreamHandler` to stdout).
- Log at `INFO`:
- start/end of run,
- discovery count and pagination progress,
- filtering result count (after date range),
- processing summary counters (`new`, `updated`, `unchanged`, `failed`),
- key warnings/errors with article ID and URL.
- Keep final JSON summary output for compatibility.

## 2. Time-range CLI (default 3 months)
Add CLI parsing in `news/update_news.py`:
- `--months N` (int, default `3`)
- `--from YYYY-MM-DD` (optional)
- `--to YYYY-MM-DD` (optional; default today UTC if `--from` used)
Rules:
- If `--from/--to` provided, they override `--months`.
- If nothing provided, use `--months 3`.
- Apply filtering against `ArticleMeta.timestamp` (UTC).
- Articles with missing/invalid timestamps are skipped with warning (inside this mode).

Internal additions:
- `parse_cli_args()`
- `compute_date_window(args) -> (start_dt, end_dt)`
- `filter_meta_by_date_range(meta_items, start_dt, end_dt)`

## 3. Chronological file paths
Change article write path generation:
- from `news/articles/{id}.json`
- to `news/articles/YYYY/MM/DD/{id}.json` (derived from article timestamp; fallback to `updated_at`, then `fetched_at` only if needed).
- Keep JSON content format exactly as-is.
- Update `article_path` in index entries accordingly.

Internal additions:
- `build_article_output_path(record, base_dir) -> Path`
- `write_article()` uses this path builder.

## 4. Runner script
Add script (recommended path: `news/run_update_news.sh`):
- Executes updater with default 3-month window:
- `./.venv/bin/python news/update_news.py --months 3`
- Includes strict shell flags and concise usage comments.

## 5. Update flow changes
`update_news()` sequence:
1. Discover metadata via APIs.
2. Filter by computed date window.
3. Process candidates (new/updated/unchanged/failed).
4. Write chronologically located article files.
5. Merge/write index sorted by timestamp desc.
6. Emit logs + final summary JSON.

## Public Interface Changes
- CLI:
- `python news/update_news.py --months 3`
- `python news/update_news.py --from 2025-10-01 --to 2025-12-31`
- Optional:
- `update_news(..., start_dt=None, end_dt=None)` internal arguments for testability.

## Minimum Test Additions
Update `tests/test_update_news.py` with focused cases:
1. `test_filter_meta_by_months_window_default_behavior`
2. `test_filter_meta_by_explicit_from_to_overrides_months`
3. `test_write_article_stores_under_yyyy_mm_dd_path`
4. `test_index_article_path_points_to_chronological_file`
5. `test_logging_emits_progress_summary` (capture logs at INFO)
6. Keep existing discovery/article parsing tests.

## Acceptance Criteria
- Running `python news/update_news.py` defaults to last 3 months.
- Logs show progress and final counters on stdout.
- New article files are saved under `news/articles/YYYY/MM/DD/`.
- `news/index.json` contains correct `article_path` values.
- Existing JSON article schema remains unchanged.
- Test suite passes with new minimum tests.

## Assumptions
- Timestamp strings from Blizzard API are UTC-compatible ISO format.
- “Reduced effort” means no automatic fetching of out-of-range historical articles unless user requests wider range.
# Update Plan: Logging, Time-Range Sync, and Chronological Storage

## Summary
Enhance `news/update_news.py` to:
1. add useful stdout logging with progress counters,
2. support range-based updates via CLI (`--months/--from/--to`) with default `--months 3`,
3. store article JSON files in chronological folders: `news/articles/YYYY/MM/DD/{id}.json`,
4. keep article JSON schema unchanged,
5. add minimum tests for new behavior.

Chosen decisions:
- Logging: `INFO` + progress counters (with optional debug support).
- Time range: CLI options, default `--months 3`.
- Range scope: only fetch articles inside the specified range.
- Storage layout: `news/articles/YYYY/MM/DD/{id}.json`.
- Add runner script to execute updater with default `--months 3`.

## Implementation Changes

## 1. Logging
Update `news/update_news.py`:
- Add `logging` setup (`StreamHandler` to stdout).
- Log at `INFO`:
- start/end of run,
- discovery count and pagination progress,
- filtering result count (after date range),
- processing summary counters (`new`, `updated`, `unchanged`, `failed`),
- key warnings/errors with article ID and URL.
- Keep final JSON summary output for compatibility.

## 2. Time-range CLI (default 3 months)
Add CLI parsing in `news/update_news.py`:
- `--months N` (int, default `3`)
- `--from YYYY-MM-DD` (optional)
- `--to YYYY-MM-DD` (optional; default today UTC if `--from` used)
Rules:
- If `--from/--to` provided, they override `--months`.
- If nothing provided, use `--months 3`.
- Apply filtering against `ArticleMeta.timestamp` (UTC).
- Articles with missing/invalid timestamps are skipped with warning (inside this mode).

Internal additions:
- `parse_cli_args()`
- `compute_date_window(args) -> (start_dt, end_dt)`
- `filter_meta_by_date_range(meta_items, start_dt, end_dt)`

## 3. Chronological file paths
Change article write path generation:
- from `news/articles/{id}.json`
- to `news/articles/YYYY/MM/DD/{id}.json` (derived from article timestamp; fallback to `updated_at`, then `fetched_at` only if needed).
- Keep JSON content format exactly as-is.
- Update `article_path` in index entries accordingly.

Internal additions:
- `build_article_output_path(record, base_dir) -> Path`
- `write_article()` uses this path builder.

## 4. Runner script
Add script (recommended path: `news/run_update_news.sh`):
- Executes updater with default 3-month window:
- `./.venv/bin/python news/update_news.py --months 3`
- Includes strict shell flags and concise usage comments.

## 5. Update flow changes
`update_news()` sequence:
1. Discover metadata via APIs.
2. Filter by computed date window.
3. Process candidates (new/updated/unchanged/failed).
4. Write chronologically located article files.
5. Merge/write index sorted by timestamp desc.
6. Emit logs + final summary JSON.

## Public Interface Changes
- CLI:
- `python news/update_news.py --months 3`
- `python news/update_news.py --from 2025-10-01 --to 2025-12-31`
- Optional:
- `update_news(..., start_dt=None, end_dt=None)` internal arguments for testability.

## Minimum Test Additions
Update `tests/test_update_news.py` with focused cases:
1. `test_filter_meta_by_months_window_default_behavior`
2. `test_filter_meta_by_explicit_from_to_overrides_months`
3. `test_write_article_stores_under_yyyy_mm_dd_path`
4. `test_index_article_path_points_to_chronological_file`
5. `test_logging_emits_progress_summary` (capture logs at INFO)
6. Keep existing discovery/article parsing tests.

## Acceptance Criteria
- Running `python news/update_news.py` defaults to last 3 months.
- Logs show progress and final counters on stdout.
- New article files are saved under `news/articles/YYYY/MM/DD/`.
- `news/index.json` contains correct `article_path` values.
- Existing JSON article schema remains unchanged.
- Test suite passes with new minimum tests.

## Assumptions
- Timestamp strings from Blizzard API are UTC-compatible ISO format.
- “Reduced effort” means no automatic fetching of out-of-range historical articles unless user requests wider range.
