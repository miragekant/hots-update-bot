# AGENTS.md

## Project Overview
- This repo contains a local Heroes of the Storm news crawler plus a Discord bot that serves cached articles.
- The crawler fetches Blizzard news metadata and article pages, then stores a local index and per-article JSON.
- The bot reads local files only when serving slash commands; user reads should not trigger network fetches.

## Key Entry Points
- `news/update_news.py`: fetches and updates the local news cache.
- `news/run_update_news.sh`: wrapper that runs the updater with the default `--months 3` sync window.
- `bot/run.py`: starts the Discord bot and its daily update loop.

## Data Layout
- `news/index.json`: lightweight article index sorted by `timestamp` descending.
- `news/articles/YYYY/MM/DD/{news_id}.json`: full article records, including parsed `body_html`.

## Environment
- Python project using a local virtualenv at `.venv`.
- Install dependencies with `pip install -r requirements.txt`.
- Runtime config is read from `.env`.
- Expected bot env vars:
  - `BOT_TOKEN`
  - `GUILD_ID`
  - `NEWS_CHANNEL_ID`
  - `DAILY_UPDATE_UTC_HOUR`
  - `DAILY_UPDATE_UTC_MINUTE`

## Common Commands
- Set up env:
  ```bash
  python -m venv .venv
  source .venv/bin/activate
  pip install -r requirements.txt
  ```
- Run tests:
  ```bash
  python -m pytest -q
  ```
- Run news update:
  ```bash
  python news/update_news.py
  ```
- Run default rolling update:
  ```bash
  ./news/run_update_news.sh
  ```
- Start the bot:
  ```bash
  python bot/run.py
  ```

## Repo Conventions
- Keep the local cache format stable unless the change explicitly updates both writer and reader paths.
- Preserve descending timestamp ordering in `news/index.json`.
- Prefer updating tests when changing pagination, repository reads, Discord message formatting, or crawler behavior.
- Keep Discord responses compatible with conservative message sizing; the codebase currently targets `1900` character chunks.
- Avoid introducing fetches into command-handling paths that are intended to read from local cache only.

## Relevant Areas
- `bot/`: Discord bot config, repository access, pagination, and message rendering.
- `news/`: crawler and update orchestration.
- `tests/`: pytest coverage for bot repository, pagination, message formatting, and updater logic.
- `plans/`: implementation notes and design plans for crawler and Discord features.

## Change Guidance
- For crawler changes, verify both index updates and per-article writes.
- For bot changes, verify slash command behavior and interactive pagination flows.
- If a change affects output formatting or pagination boundaries, add or update tests first or alongside the code change.
