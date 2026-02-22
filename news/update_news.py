from __future__ import annotations

import argparse
import hashlib
import json
import logging
import re
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlencode, urljoin

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://news.blizzard.com"
LOCALE = "en-us"
PRODUCT = "heroes-of-the-storm"
NEWS_API_URL = f"{BASE_URL}/{LOCALE}/api/news/{PRODUCT}"
FEED_API_URL = f"{BASE_URL}/{LOCALE}/api/feed/{PRODUCT}"
DEFAULT_DATA_DIR = Path("news") / "articles"
DEFAULT_INDEX_PATH = Path("news") / "index.json"
REQUEST_TIMEOUT = 30
MAX_RETRIES = 3
DEFAULT_MONTHS = 3

logger = logging.getLogger("hots_update")


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


def configure_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logger.setLevel(level)
    logger.handlers.clear()
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(level)
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(handler)
    logger.propagate = False


def parse_cli_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Update HOTS news articles")
    parser.add_argument("--months", type=int, default=DEFAULT_MONTHS, help="lookback window in months")
    parser.add_argument("--from", dest="from_date", type=str, default=None, help="start date YYYY-MM-DD")
    parser.add_argument("--to", dest="to_date", type=str, default=None, help="end date YYYY-MM-DD")
    parser.add_argument("--limit", type=int, default=None, help="max number of candidate articles")
    parser.add_argument("--verbose", action="store_true", help="enable debug logging")
    return parser.parse_args()


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _now_iso() -> str:
    return _now_utc().isoformat()


def _parse_iso_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None


def _parse_date(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%d").replace(tzinfo=timezone.utc)


def compute_date_window(
    months: int = DEFAULT_MONTHS,
    from_date: str | None = None,
    to_date: str | None = None,
) -> tuple[datetime, datetime]:
    if from_date or to_date:
        end = _parse_date(to_date) if to_date else _now_utc()
        start = _parse_date(from_date) if from_date else end - timedelta(days=30 * months)
    else:
        end = _now_utc()
        start = end - timedelta(days=30 * months)

    if start > end:
        raise ValueError("start date must be <= end date")

    return start, end


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
            logger.warning("request failed (%s/%s) url=%s error=%s", attempt + 1, MAX_RETRIES, url, exc)
            if attempt < MAX_RETRIES - 1:
                time.sleep(0.5 * (attempt + 1))
    assert last_error is not None
    raise last_error


def _request_json(url: str, timeout: int = REQUEST_TIMEOUT) -> dict[str, Any]:
    return json.loads(_request_text(url, timeout=timeout))


def fetch_article_html(url: str) -> str:
    return _request_text(url)


def fetch_news_api_json() -> dict[str, Any]:
    return _request_json(NEWS_API_URL)


def fetch_feed_page_json(offset: int = 0, filters: list[str] | None = None) -> dict[str, Any]:
    params: list[tuple[str, str]] = [("offset", str(offset))]
    for item in filters or []:
        params.append(("feedCxpProductIds[]", item))
    return _request_json(f"{FEED_API_URL}?{urlencode(params)}")


def _get_item_properties(group: dict[str, Any]) -> dict[str, Any]:
    if isinstance(group.get("properties"), dict):
        return group.get("properties") or {}
    content_items = group.get("contentItems") or []
    first = content_items[0] if content_items else {}
    return first.get("properties") or {}


def _to_meta(group: dict[str, Any], section: str) -> ArticleMeta | None:
    props = _get_item_properties(group)
    news_path = props.get("newsPath")
    if not news_path:
        return None

    url = urljoin(BASE_URL, news_path)
    news_id = _extract_news_id(url)
    if not news_id:
        return None

    static_asset = props.get("staticAsset") or {}
    return ArticleMeta(
        news_id=news_id,
        url=url,
        title=(props.get("title") or "").strip(),
        description=(props.get("summary") or "").strip(),
        section=section,
        timestamp=props.get("lastUpdated"),
        image_url=static_asset.get("imageUrl"),
    )


def _extract_featured_groups(news_json: dict[str, Any]) -> list[dict[str, Any]]:
    sections = news_json.get("sections") or []
    for section in sections:
        if section.get("name") == "Featured":
            return section.get("contentGroups") or []
    return []


def _extract_feed_groups(payload: dict[str, Any]) -> list[dict[str, Any]]:
    feed = payload.get("feed")
    if isinstance(feed, dict):
        return feed.get("contentItems") or []
    return payload.get("contentItems") or []


def discover_all_article_meta(start_dt: datetime | None = None) -> list[ArticleMeta]:
    seen: set[str] = set()
    results: list[ArticleMeta] = []

    root = fetch_news_api_json()

    for group in _extract_featured_groups(root):
        meta = _to_meta(group, "featured")
        if meta and meta.news_id not in seen:
            seen.add(meta.news_id)
            results.append(meta)

    for group in _extract_feed_groups(root):
        meta = _to_meta(group, "latest")
        if meta and meta.news_id not in seen:
            seen.add(meta.news_id)
            results.append(meta)

    feed_state = root.get("feed") or {}
    pagination = feed_state.get("pagination") or {}
    offset = pagination.get("offset", 0)
    limit = pagination.get("limit", 0)
    has_next = bool(pagination.get("hasNextPage"))
    pages = 1

    while has_next:
        offset = offset + limit
        page = fetch_feed_page_json(offset=offset)
        pages += 1
        page_has_in_range_item = False
        for group in _extract_feed_groups(page):
            meta = _to_meta(group, "latest")
            if meta and meta.news_id not in seen:
                seen.add(meta.news_id)
                results.append(meta)
            if start_dt is not None and meta is not None:
                ts = _parse_iso_datetime(meta.timestamp)
                if ts is not None and ts >= start_dt:
                    page_has_in_range_item = True

        page_pagination = page.get("pagination") or {}
        offset = page_pagination.get("offset", offset)
        limit = page_pagination.get("limit", limit)
        has_next = bool(page_pagination.get("hasNextPage"))
        if start_dt is not None and not page_has_in_range_item:
            logger.info("pagination stopped early at page=%s (older than start date)", pages)
            break

    logger.info("discovery finished pages=%s candidates=%s", pages, len(results))
    return results


def filter_meta_by_date_range(meta_items: list[ArticleMeta], start_dt: datetime, end_dt: datetime) -> list[ArticleMeta]:
    filtered: list[ArticleMeta] = []
    skipped_invalid = 0
    for item in meta_items:
        ts = _parse_iso_datetime(item.timestamp)
        if ts is None:
            skipped_invalid += 1
            logger.warning("skip article with invalid timestamp news_id=%s timestamp=%s", item.news_id, item.timestamp)
            continue
        if start_dt <= ts <= end_dt:
            filtered.append(item)

    logger.info(
        "date filter applied start=%s end=%s kept=%s skipped_invalid=%s",
        start_dt.isoformat(),
        end_dt.isoformat(),
        len(filtered),
        skipped_invalid,
    )
    return filtered


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


def build_article_output_path(record: ArticleRecord, base_dir: Path = DEFAULT_DATA_DIR) -> Path:
    for candidate in (record.timestamp, record.updated_at, record.published_at, record.fetched_at):
        dt = _parse_iso_datetime(candidate)
        if dt is not None:
            return base_dir / f"{dt.year:04d}" / f"{dt.month:02d}" / f"{dt.day:02d}" / f"{record.news_id}.json"
    now = _now_utc()
    return base_dir / f"{now.year:04d}" / f"{now.month:02d}" / f"{now.day:02d}" / f"{record.news_id}.json"


def write_article(record: ArticleRecord, dir_path: Path = DEFAULT_DATA_DIR) -> Path:
    path = build_article_output_path(record, dir_path)
    path.parent.mkdir(parents=True, exist_ok=True)
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
    start_dt: datetime | None = None,
    end_dt: datetime | None = None,
) -> UpdateStats:
    stats = UpdateStats()
    index = load_index(index_path)
    existing = {item["news_id"]: item for item in index.get("articles", [])}

    logger.info("starting update index=%s article_dir=%s", index_path, article_dir)

    candidates = discover_all_article_meta(start_dt=start_dt)
    if start_dt is not None and end_dt is not None:
        candidates = filter_meta_by_date_range(candidates, start_dt, end_dt)

    if limit is not None:
        candidates = candidates[:limit]
        logger.info("limit applied candidates=%s", len(candidates))

    changed_index_items: list[dict[str, Any]] = []

    for i, meta in enumerate(candidates, start=1):
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
                logger.info("[%s/%s] updated news_id=%s", i, len(candidates), meta.news_id)
            else:
                stats.new += 1
                logger.info("[%s/%s] new news_id=%s", i, len(candidates), meta.news_id)
        except Exception as exc:
            stats.failed += 1
            logger.error("[%s/%s] failed news_id=%s url=%s error=%s", i, len(candidates), meta.news_id, meta.url, exc)

    merged = merge_updates(index, changed_index_items)
    write_index(merged, index_path)

    logger.info(
        "update finished new=%s updated=%s unchanged=%s failed=%s total_index=%s",
        stats.new,
        stats.updated,
        stats.unchanged,
        stats.failed,
        merged.get("count", 0),
    )
    return stats


def main() -> None:
    args = parse_cli_args()
    configure_logging(verbose=args.verbose)

    start_dt, end_dt = compute_date_window(months=args.months, from_date=args.from_date, to_date=args.to_date)
    result = update_news(limit=args.limit, start_dt=start_dt, end_dt=end_dt)
    print(json.dumps(asdict(result), indent=2))


if __name__ == "__main__":
    main()
