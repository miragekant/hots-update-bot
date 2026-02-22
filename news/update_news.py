from __future__ import annotations

import hashlib
import json
import re
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

FEED_URL = "https://news.blizzard.com/en-us/feed/heroes-of-the-storm"
DEFAULT_DATA_DIR = Path("news") / "articles"
DEFAULT_INDEX_PATH = Path("news") / "index.json"
REQUEST_TIMEOUT = 30
MAX_RETRIES = 3


@dataclass
class ArticleMeta:
    news_id: str
    url: str
    title: str
    description: str
    section: str
    timestamp: str | None
    image_url: str | None


@dataclass
class ArticleDetail:
    author: str | None
    published_at: str | None
    updated_at: str | None
    header_image_url: str | None
    body_html: str


@dataclass
class ArticleRecord:
    news_id: str
    url: str
    title: str
    description: str
    section: str
    timestamp: str | None
    image_url: str | None
    author: str | None
    published_at: str | None
    updated_at: str | None
    header_image_url: str | None
    body_html: str
    fetched_at: str
    content_hash: str


@dataclass
class UpdateStats:
    new: int = 0
    updated: int = 0
    unchanged: int = 0
    failed: int = 0


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _extract_news_id(url: str) -> str | None:
    match = re.search(r"/article/(\d+)", url)
    return match.group(1) if match else None


def _request_text(url: str, timeout: int = REQUEST_TIMEOUT) -> str:
    last_error: Exception | None = None
    for attempt in range(MAX_RETRIES):
        try:
            response = requests.get(url, timeout=timeout)
            response.raise_for_status()
            return response.text
        except requests.RequestException as exc:
            last_error = exc
            if attempt < MAX_RETRIES - 1:
                time.sleep(0.5 * (attempt + 1))
    assert last_error is not None
    raise last_error


def fetch_feed_html() -> str:
    return _request_text(FEED_URL)


def fetch_article_html(url: str) -> str:
    return _request_text(url)


def parse_feed(html: str, base_url: str = FEED_URL) -> list[ArticleMeta]:
    soup = BeautifulSoup(html, "html.parser")

    selectors = {
        "featured": "blz-news-featured-cards.section-featured-news blz-news.featured-news > blz-news-card",
        "latest": ".LatestNews .LatestNews-feed blz-news-feed ol.card-list > li > blz-news-card",
    }

    seen_ids: set[str] = set()
    results: list[ArticleMeta] = []

    for section, selector in selectors.items():
        for card in soup.select(selector):
            href = card.get("href")
            if not href:
                continue

            url = urljoin(base_url, href)
            news_id = _extract_news_id(url)
            if not news_id or news_id in seen_ids:
                continue

            title_el = card.select_one("h1[slot='heading']")
            description_el = card.select_one("p[slot='description']")
            timestamp_el = card.select_one("blz-timestamp[slot='metadata']")
            image_el = card.select_one("blz-image[slot='image']")

            seen_ids.add(news_id)
            results.append(
                ArticleMeta(
                    news_id=news_id,
                    url=url,
                    title=title_el.get_text(strip=True) if title_el else "",
                    description=description_el.get_text(strip=True) if description_el else "",
                    section=section,
                    timestamp=timestamp_el.get("timestamp") if timestamp_el else None,
                    image_url=urljoin(base_url, image_el.get("src")) if image_el and image_el.get("src") else None,
                )
            )

    return results


def parse_article(html: str, url: str) -> ArticleDetail:
    soup = BeautifulSoup(html, "html.parser")

    root = soup.select_one("article.Content")
    if root is None:
        raise ValueError("article root not found")

    body = root.select_one("section.blog")
    if body is None:
        raise ValueError("article body not found")

    for a in body.select("a[href]"):
        a["href"] = urljoin(url, a["href"])

    for img in body.select("img[src]"):
        img["src"] = urljoin(url, img["src"])

    author_el = root.select_one(".details .author")
    timestamp_el = root.select_one("blz-timestamp[timestamp]")
    # Blizzard pages often have only one canonical update moment on this element.
    updated_at = timestamp_el.get("timestamp") if timestamp_el else None
    header_image = root.select_one("header.ContentHeader > blz-image[src]")

    return ArticleDetail(
        author=author_el.get_text(strip=True) if author_el else None,
        published_at=updated_at,
        updated_at=updated_at,
        header_image_url=urljoin(url, header_image.get("src")) if header_image else None,
        body_html=body.decode_contents(),
    )


def _record_from_meta_and_detail(meta: ArticleMeta, detail: ArticleDetail) -> ArticleRecord:
    payload = {
        **asdict(meta),
        **asdict(detail),
    }
    content_hash = hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()

    return ArticleRecord(
        **payload,
        fetched_at=_now_iso(),
        content_hash=content_hash,
    )


def load_index(path: Path = DEFAULT_INDEX_PATH) -> dict[str, Any]:
    if not path.exists():
        return {"generated_at": None, "count": 0, "articles": []}
    return json.loads(path.read_text(encoding="utf-8"))


def _article_sort_key(article: dict[str, Any]) -> tuple[str, str]:
    ts = article.get("timestamp") or ""
    return (ts, article.get("news_id") or "")


def merge_updates(index: dict[str, Any], updated_articles: list[dict[str, Any]]) -> dict[str, Any]:
    by_id: dict[str, dict[str, Any]] = {item["news_id"]: item for item in index.get("articles", [])}
    for article in updated_articles:
        by_id[article["news_id"]] = article

    articles = sorted(by_id.values(), key=_article_sort_key, reverse=True)
    return {
        "generated_at": _now_iso(),
        "count": len(articles),
        "articles": articles,
    }


def write_article(record: ArticleRecord, dir_path: Path = DEFAULT_DATA_DIR) -> Path:
    dir_path.mkdir(parents=True, exist_ok=True)
    path = dir_path / f"{record.news_id}.json"
    path.write_text(json.dumps(asdict(record), ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def write_index(index: dict[str, Any], path: Path = DEFAULT_INDEX_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")


def _index_item(record: ArticleRecord, article_path: Path) -> dict[str, Any]:
    return {
        "news_id": record.news_id,
        "url": record.url,
        "title": record.title,
        "timestamp": record.timestamp,
        "updated_at": record.updated_at,
        "section": record.section,
        "article_path": str(article_path),
    }


def update_news(
    limit: int | None = None,
    index_path: Path = DEFAULT_INDEX_PATH,
    article_dir: Path = DEFAULT_DATA_DIR,
) -> UpdateStats:
    stats = UpdateStats()
    index = load_index(index_path)
    existing = {item["news_id"]: item for item in index.get("articles", [])}

    feed_html = fetch_feed_html()
    candidates = parse_feed(feed_html)
    if limit is not None:
        candidates = candidates[:limit]

    changed_index_items: list[dict[str, Any]] = []

    for meta in candidates:
        existing_item = existing.get(meta.news_id)
        if existing_item and existing_item.get("timestamp") == meta.timestamp:
            stats.unchanged += 1
            continue

        try:
            article_html = fetch_article_html(meta.url)
            detail = parse_article(article_html, meta.url)
            record = _record_from_meta_and_detail(meta, detail)
            path = write_article(record, article_dir)
            changed_index_items.append(_index_item(record, path))

            if existing_item:
                stats.updated += 1
            else:
                stats.new += 1
        except Exception:
            stats.failed += 1

    merged = merge_updates(index, changed_index_items)
    write_index(merged, index_path)
    return stats


if __name__ == "__main__":
    result = update_news()
    print(json.dumps(asdict(result), indent=2))
