# Discord News Bot Implementation Plan (Implemented)

## Summary
Integrate a Discord bot with the existing local HOTS news pipeline so users can browse cached articles via slash commands, with scheduled daily updates and safe message formatting.

## Implemented Scope
- Added `/latest` to show the latest local article.
- Added `/news` with optional `year` filter, pagination, and article selection.
- Added message formatting utilities for article metadata and body text chunking.
- Added a daily in-bot updater that runs at configured UTC time without blocking command handling.
- Kept local-news read path cache-first (no fetch on user read commands).
- Added minimum unit tests and updated documentation.

## Architecture and Modules
- `bot/config.py`
  - `BotConfig` dataclass for runtime configuration.
  - `load_config()` with env parsing and validation.

- `bot/repository.py`
  - `NewsRepository` for local index/article access.
  - APIs:
    - `get_latest_article()`
    - `list_articles(year, offset, limit)`
    - `get_article_by_news_id(news_id)`

- `bot/message.py`
  - HTML to Discord text conversion.
  - Safe chunk splitting (default 1900 chars).
  - Embed builders:
    - `format_article_embed(...)`
    - `format_article_body_chunks(...)`
    - `format_news_list_embed(...)`

- `bot/pagination.py`
  - `NewsPaginationView` (`discord.ui.View`) with:
    - Prev/Next page buttons
    - Select menu for opening full article
  - Helpers:
    - `compute_total_pages(...)`
    - `page_slice(...)`

- `bot/run.py`
  - Discord client wiring and command registration.
  - `/hello`, `/latest`, `/news` command handlers.
  - Daily update loop using `asyncio.to_thread(update_news)`.
  - Locking to prevent overlapping update jobs.
  - Daily summary + latest article post to configured channel.

## Public Interfaces
- Slash commands:
  - `/latest`
  - `/news year:<optional int>`

- Environment variables:
  - `BOT_TOKEN` (required)
  - `GUILD_ID` (required)
  - `NEWS_CHANNEL_ID` (required)
  - `DAILY_UPDATE_UTC_HOUR` (optional, default `15`)
  - `DAILY_UPDATE_UTC_MINUTE` (optional, default `0`)

## Message and UX Rules
- Uses embeds for metadata (title, author, date, section, image).
- Converts stored `body_html` to readable text.
- Splits long content into multiple messages to stay below Discord limits.
- `/news` page size is 5 items per page.
- Interaction controls are restricted to the requesting user.

## Scheduler Behavior
- Daily task is started after client readiness.
- First run is aligned to configured UTC hour/minute.
- Subsequent runs occur every 24 hours.
- Updater execution is offloaded to a worker thread to avoid event-loop blocking.

## Tests Added
- `tests/test_bot_message.py`
  - chunk size safety
  - link conversion behavior
  - list embed paging footer

- `tests/test_bot_repository.py`
  - latest article resolution
  - year filtering
  - article-by-id loading

- `tests/test_bot_pagination.py`
  - page count calculations
  - page slicing

- `tests/conftest.py`
  - ensure project root import path for tests

## Validation Performed
- Ran full test suite: `pytest -q`
- Result: all tests passing.

## Documentation
- Updated `README.md` with:
  - bot setup and `.env` configuration
  - bot run command
  - command behavior details
  - note on conservative message chunk size

## Assumptions and Defaults
- Bot process is long-running and hosts the scheduler.
- Daily post target is a single configured channel.
- Cached local files are source of truth for read commands.
- Existing crawler data schema remains unchanged.
