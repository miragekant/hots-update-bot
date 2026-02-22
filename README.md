# HOTS Update Bot

Minimal crawler for Heroes of the Storm news from Blizzard.

## What It Does
- Reads the HOTS news feed page.
- Extracts article metadata from Featured + Latest sections.
- Fetches each article page.
- Preserves article body HTML structure from `article.Content section.blog`.
- Stores structured output and supports incremental updates.

## Data Output
- `news/index.json`: lightweight index, sorted by `timestamp` (newest first).
- `news/articles/{news_id}.json`: full per-article record including `body_html`.

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

## Run Tests
```bash
python -m pytest -q
```

## Notes
- Feed URL: `https://news.blizzard.com/en-us/feed/heroes-of-the-storm`
- Uses `requests` + `beautifulsoup4` for parsing.
- Retry/backoff is included for HTTP requests.
