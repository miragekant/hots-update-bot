# Fix `update_news.py` for Full Historical Sync

## Summary
Update discovery from DOM scraping to Blizzard JSON APIs so runs no longer return zero items, and ensure article files are stored in `news/articles/` with `news/index.json` as the index.
Chosen behavior:
- Discovery source: Blizzard JSON API
- Backfill mode: full pagination on every run (fetch only missing/changed article pages)
- Storage subfolder: `news/articles`

## Why Current Behavior Is Zero
- `parse_feed()` currently looks for `blz-news-card` in raw feed HTML.
- Those cards are JS-rendered and not present in server HTML.
- Result: no candidates, stats all zero.

## Implementation Changes

### 1. Replace feed discovery path
- Add API fetchers:
- `GET /en-us/api/news/heroes-of-the-storm` for initial payload (featured + feed metadata)
- `GET /en-us/api/feed/heroes-of-the-storm?offset={offset}&feedCxpProductIds[]=...` for pagination
- Build `ArticleMeta` from API `contentItems` and normalize to existing schema:
- `news_id`, `url`, `title`, `description`, `timestamp`, `image_url`, `section`

### 2. Full historical pagination each run
- Iterate pages until `hasNextPage == false`.
- Deduplicate by `news_id` across featured/latest/paginated feed.
- Keep a stable `seen_ids` set.

### 3. Incremental article fetch logic
- For each discovered meta item:
- If `news_id` missing in index: fetch article page and save.
- If present but timestamp changed: refetch and overwrite.
- Else mark unchanged.
- Keep current article body extraction from `article.Content section.blog` and URL normalization.

### 4. Storage layout (explicit)
- Index: `news/index.json`
- Articles: `news/articles/{news_id}.json`
- Ensure `article_path` in index always points to `news/articles/{id}.json`.

### 5. Backward-safe merge behavior
- Merge newly processed items into existing index by `news_id`.
- Sort descending by `timestamp`.
- Preserve existing records for IDs no longer returned by upstream (history retention).

## Public Interface / Type Updates
- Keep `update_news(limit: int | None = None, index_path: Path = ..., article_dir: Path = ...)`.
- `limit` applies to discovered candidates after full list assembly.
- Internally add:
- `fetch_news_api_json()`
- `fetch_feed_page_json(offset: int, filters: list[str] | None = None)`
- `parse_api_items(...) -> list[ArticleMeta]`

## Tests (minimum additions)
1. `test_api_discovery_extracts_items_from_news_and_feed_pages`
2. `test_api_discovery_paginates_until_has_next_page_false`
3. `test_api_discovery_dedupes_featured_and_feed_duplicates`
4. `test_update_news_full_scan_fetches_missing_old_article`
5. `test_update_news_writes_article_path_under_news_articles`
6. Keep existing article-body preservation test.

## Acceptance Criteria
- Running `python news/update_news.py` on empty local storage yields `new > 0`.
- Re-running without upstream changes yields mostly `unchanged > 0`, `new == 0`.
- `news/index.json` is timestamp-sorted descending and points to `news/articles/*.json`.
- Older articles absent locally are added automatically in subsequent runs.

## Assumptions / Defaults
- Locale remains `en-us`.
- API endpoints remain publicly accessible without auth.
- Timestamp comparison remains the refresh trigger for “updated”.
