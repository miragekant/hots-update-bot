# HOTS Update Bot

Local HOTS news crawler plus Discord bot for browsing cached articles.

## What It Does
- Fetches HOTS news metadata + article pages from Blizzard.
- Stores local index + full article JSON.
- Supports incremental updates with date-range filtering.
- Exposes Discord slash commands for local news browsing:
  - `/latest`
  - `/news year:<optional>`
- Runs a daily non-blocking update loop inside the bot process.

## Data Output
- `news/index.json`: lightweight index, sorted by `timestamp` (newest first).
- `news/articles/YYYY/MM/DD/{news_id}.json`: full per-article record including `body_html`.

## Setup
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Run Update
```bash
python news/update_news.py
```

This fetches feed + articles, writes updated files, and prints update stats:
- `new`
- `updated`
- `unchanged`
- `failed`

Common options:
```bash
python news/update_news.py --months 3
python news/update_news.py --from 2025-01-01 --to 2025-12-31
```

## Run Discord Bot
Create `.env` with:
```bash
BOT_TOKEN=your_discord_bot_token
GUILD_ID=123456789012345678
NEWS_CHANNEL_ID=123456789012345678
DAILY_UPDATE_UTC_HOUR=15
DAILY_UPDATE_UTC_MINUTE=0
```

Start bot:
```bash
python bot/run.py
```

Behavior:
- `/latest` shows latest local article in a rich embed with Prev/Next buttons for article pages.
- `/news` shows paginated local list (5 per page), optional `year` filter, and interactive article selection.
- Selecting an article opens a rich embed with button-based page navigation.
- Daily job runs at configured UTC time, updates local cache, and posts update summary + newest article when changes exist.
- Command responses read from local files only (no fetch on user read request).
- Article body rendering maps HTML structure (headings/lists/quotes/code/links) to compact Discord markdown.

## Run Tests
```bash
python -m pytest -q
```

## Plans
- Discord-related implementation plans: `plans/discord/`
- News crawler/updater plans: `plans/news/`

## Notes
- Uses `requests` + `beautifulsoup4` for crawler parsing.
- Uses `discord.py` for slash commands and interaction components.
- Discord message chunking uses a conservative `1900` character limit.
