# AGENTS.md

## Overview
- Repo: local Heroes of the Storm news crawler plus Discord bot.
- Crawler fetches Blizzard news and writes local cache files.
- Bot command paths should read local cache only; do not add user-triggered fetches.

## Entry Points
- `news/update_news.py`: sync news cache.
- `news/run_update_news.sh`: default rolling sync (`--months 3`).
- `bot/run.py`: start Discord bot and daily update loop.

## Data
- `news/index.json`: article index, newest first by `timestamp`.
- `news/articles/YYYY/MM/DD/{news_id}.json`: full article payloads with `body_html`.
- `heroesprofile/`: cached HeroesProfile data used by `/hero`, `/map`, `/patch`, and `/talentbuilder`.

## Environment
- Use local venv: `.venv`.
- Install: `pip install -r requirements.txt`
- Config comes from `.env`.
- Bot env vars: `BOT_TOKEN`, `GUILD_ID`, `NEWS_CHANNEL_ID`, `DAILY_UPDATE_UTC_HOUR`, `DAILY_UPDATE_UTC_MINUTE`.

## Commands
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
.venv/bin/python -m pytest -q
.venv/bin/python news/update_news.py
./news/run_update_news.sh
.venv/bin/python bot/run.py
```

## Change Rules
- Keep cache formats stable unless writer and reader paths are updated together.
- Preserve descending order in `news/index.json`.
- Keep Discord output within the repo's conservative `1900` character target.
- Update tests when changing pagination, repository reads, Discord formatting, or crawler behavior.
- For crawler changes, verify both index writes and per-article writes.
- For bot changes, verify slash-command behavior and interactive pagination flows.

## Code Areas
- `bot/`: Discord commands, repository access, formatting, pagination.
- `news/`: crawler and update orchestration.
- `tests/`: pytest coverage for bot and updater behavior.
- `plans/`: implementation notes and design plans.
