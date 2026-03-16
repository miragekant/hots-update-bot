# HOTS Update Bot

Local HOTS news crawler plus Discord bot for browsing cached articles.

## What It Does
- Fetches HOTS news metadata + article pages from Blizzard.
- Stores local index + full article JSON.
- Supports incremental updates with date-range filtering.
- Imports HeroesProfile general API data into local cache files.
- Exposes Discord slash commands for local news browsing:
  - `/latest`
  - `/news year:<optional>`
  - `/hero name:<optional>`
  - `/map name:<optional>`
  - `/patch version:<optional>`
  - `/talentbuilder hero:<optional> talent_string:<optional>`
- Runs a daily non-blocking update loop inside the bot process.

## Data Output
- `news/index.json`: lightweight index, sorted by `timestamp` (newest first).
- `news/articles/YYYY/MM/DD/{news_id}.json`: full per-article record including `body_html`.
- `heroesprofile/patches/index.json`: cached HeroesProfile patch families + builds.
- `heroesprofile/maps/index.json`: cached HeroesProfile maps.
- `heroesprofile/heroes/index.json`: cached hero summaries.
- `heroesprofile/heroes/by_name/{slug}.json`: full hero records.
- `heroesprofile/talents/by_hero/{slug}.json`: cached talents grouped by tier for each hero.

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

## Run HeroesProfile Update
```bash
python heroesprofile/update_data.py
```

Common options:
```bash
python heroesprofile/update_data.py --only heroes,talents
python heroesprofile/update_data.py --workers 4 --verbose
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
- `/hero`, `/map`, and `/patch` accept an optional lookup value; when omitted, each command opens a cache-backed paginated list with a select menu for drilling into a local record.
- `/hero` detail views show direct buttons for `Summary` and each talent tier page.
- `/map` reads cached HeroesProfile map data.
- `/patch` reads cached HeroesProfile patch-family data, including full build lookups.
- `/talentbuilder` opens an ephemeral, cache-only builder for choosing a hero, selecting talents tier by tier, revising prior tiers, optionally naming the build, and exporting a HOTS talent string in a copy-friendly code block.
- `/talentbuilder` can also parse an existing HOTS talent string such as `[T3211221,Leoric]`, validate it against the local cache, and open a paginated per-tier breakdown.
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
- HeroesProfile API plans: `plans/heroesprofile/`

## Notes
- Uses `requests` + `beautifulsoup4` for crawler parsing.
- Uses `requests` for HeroesProfile API syncing.
- Uses `discord.py` for slash commands and interaction components.
- Discord message chunking uses a conservative `1900` character limit.
