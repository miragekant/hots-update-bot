from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _parse_iso_datetime(value: str | None) -> datetime:
    if not value:
        return datetime.min.replace(tzinfo=timezone.utc)
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return datetime.min.replace(tzinfo=timezone.utc)


@dataclass
class NewsRepository:
    index_path: Path = Path("news") / "index.json"

    def _read_index(self) -> dict[str, Any]:
        if not self.index_path.exists():
            return {"articles": []}
        return json.loads(self.index_path.read_text(encoding="utf-8"))

    def _sorted_articles(self) -> list[dict[str, Any]]:
        articles = list(self._read_index().get("articles", []))
        return sorted(articles, key=lambda item: _parse_iso_datetime(item.get("timestamp")), reverse=True)

    def get_latest_article(self) -> dict[str, Any] | None:
        articles = self._sorted_articles()
        return articles[0] if articles else None

    def list_articles(self, year: int | None = None, offset: int = 0, limit: int = 5) -> tuple[list[dict[str, Any]], int]:
        items = self._sorted_articles()
        if year is not None:
            filtered: list[dict[str, Any]] = []
            for item in items:
                ts = _parse_iso_datetime(item.get("timestamp"))
                if ts.year == year:
                    filtered.append(item)
            items = filtered

        total = len(items)
        if offset < 0:
            offset = 0
        if limit < 0:
            limit = 0
        return items[offset : offset + limit], total

    def get_article_by_news_id(self, news_id: str) -> dict[str, Any] | None:
        for item in self._sorted_articles():
            if item.get("news_id") != news_id:
                continue
            raw_path = item.get("article_path")
            if not isinstance(raw_path, str) or raw_path.strip() == "":
                return None
            article_path = Path(raw_path)
            if not article_path.is_absolute():
                article_path = Path.cwd() / article_path
            if not article_path.exists():
                return None
            return json.loads(article_path.read_text(encoding="utf-8"))
        return None
