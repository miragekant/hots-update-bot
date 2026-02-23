# HOTS News Crawler Update Plan

## Summary
Update the crawler using `requests + BeautifulSoup` to:
1. fetch article list + metadata from the HOTS news feed page,
2. fetch each article page and preserve body HTML structure,
3. store data in structured JSON files sorted by timestamp,
4. support incremental updates (new/changed articles only),
5. add minimum-effort unit tests for parser/storage/update functions.

## Strategy (Chosen)
- Stack: `requests + bs4` (minimal effort, easiest to test).
- Storage: `JSON index + per-article files`.
- Body preservation: store sanitized/normalized `body_html` (structure retained), plus optional plain text summary.
- Incremental update key: `news_id` (from URL) + `updated_at` timestamp check.

## Source Selectors And Extraction Rules

### Feed page
URL: `https://news.blizzard.com/en-us/feed/heroes-of-the-storm`

- Featured cards: `blz-news-featured-cards.section-featured-news blz-news.featured-news > blz-news-card`
- Latest cards: `.LatestNews .LatestNews-feed blz-news-feed ol.card-list > li > blz-news-card`
- Per-card fields:
- URL: `blz-news-card[href]::attr(href)`
- Title: `h1[slot="heading"]`
- Subheading: `h2[slot="subheading"]`
- Description: `p[slot="description"]`
- Timestamp element: `blz-timestamp[slot="metadata"]` (use `timestamp` attr when available)
- Hero image: `blz-image[slot="image"]` (`src`, `alt`)

### Article page
Example: `https://news.blizzard.com/en-us/article/24229032/...`

- Article root: `article.Content`
- Title: `article.Content h1[slot="heading"]`
- Author: `article.Content .details .author`
- Published timestamp: `article.Content blz-timestamp[timestamp]`
- Header image: `article.Content header.ContentHeader > blz-image[src]`
- Body container to preserve structure: `article.Content section.blog`
- Preserve with `decode_contents()` after URL normalization for `a[href]` and `img[src]`.

## Data Model / Interfaces

### Functions
- `fetch_feed_html() -> str`
- `parse_feed(html: str, base_url: str) -> list[ArticleMeta]`
- `fetch_article_html(url: str) -> str`
- `parse_article(html: str, url: str) -> ArticleDetail`
- `load_index(path: str) -> IndexFile`
- `merge_updates(index: IndexFile, articles: list[ArticleRecord]) -> IndexFile`
- `write_article(record: ArticleRecord, dir_path: str) -> None`
- `write_index(index: IndexFile, path: str) -> None`
- `update_news(limit: int | None = None) -> UpdateStats`

### Types
- `ArticleMeta`:
- `news_id`, `url`, `title`, `description`, `section` (`featured|latest`), `timestamp`, `image_url`
- `ArticleDetail`:
- `author`, `published_at`, `updated_at`, `header_image_url`, `body_html`
- `ArticleRecord`:
- `meta + detail`, plus `fetched_at`, `content_hash`
- `IndexFile`:
- `generated_at`, `count`, `articles` (sorted desc by timestamp)

## Storage Layout
- `news/index.json` (sorted by timestamp desc)
- `news/articles/{news_id}.json` (full record per article)

`index.json` stores lightweight fields + pointer:
- `news_id`, `url`, `title`, `timestamp`, `updated_at`, `section`, `article_path`.

## Update Behavior
1. Parse feed and build candidate list.
2. For each candidate:
- If `news_id` not in index: fetch + parse + save.
- If exists and `timestamp/updated_at` differs: refetch + overwrite.
- Else skip.
3. Rebuild index sorted desc by timestamp.
4. Output update stats (`new`, `updated`, `unchanged`, `failed`).

## Minimal Unit Tests
Use `pytest` with local HTML fixtures.

- `test_parse_feed_extracts_featured_and_latest_cards`
- `test_parse_feed_deduplicates_same_article_across_sections`
- `test_parse_article_extracts_metadata_and_body_container`
- `test_parse_article_preserves_nested_lists_headings_links_images_in_body_html`
- `test_merge_updates_orders_by_timestamp_desc`
- `test_incremental_update_skips_unchanged_articles`
- `test_incremental_update_updates_changed_article`

## Code Review Plan
After implementation:
1. Review parsing correctness against saved fixtures.
2. Review update idempotency (running twice without site changes yields no writes).
3. Review schema consistency between `index.json` and per-article files.
4. Review test coverage for parsing + merge/update paths.
5. Review failure handling (network errors, missing selectors, partial write safety).

## Assumptions / Defaults
- Locale fixed to `en-us`.
- `requests` timeout and simple retry/backoff will be added (small, local helper).
- Body HTML is preserved structurally; no aggressive cleanup beyond URL normalization.
- Sorting key defaults to article timestamp descending.
