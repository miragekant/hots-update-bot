import json
from pathlib import Path

from bot.repository import NewsRepository


def _write(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


def test_repository_latest_and_year_filter(tmp_path: Path):
    article_1 = tmp_path / "articles" / "2024" / "01" / "01" / "1.json"
    article_2 = tmp_path / "articles" / "2025" / "06" / "01" / "2.json"
    _write(article_1, {"news_id": "1", "title": "Old", "body_html": "<p>x</p>"})
    _write(article_2, {"news_id": "2", "title": "New", "body_html": "<p>y</p>"})

    index = {
        "articles": [
            {
                "news_id": "1",
                "title": "Old",
                "timestamp": "2024-01-01T00:00:00Z",
                "article_path": str(article_1),
            },
            {
                "news_id": "2",
                "title": "New",
                "timestamp": "2025-06-01T00:00:00Z",
                "article_path": str(article_2),
            },
        ]
    }
    index_path = tmp_path / "index.json"
    _write(index_path, index)

    repo = NewsRepository(index_path=index_path)
    latest = repo.get_latest_article()
    assert latest is not None
    assert latest["news_id"] == "2"

    items_2024, total_2024 = repo.list_articles(year=2024, offset=0, limit=5)
    assert total_2024 == 1
    assert items_2024[0]["news_id"] == "1"


def test_repository_get_article_by_news_id(tmp_path: Path):
    article = tmp_path / "articles" / "2025" / "01" / "01" / "42.json"
    _write(article, {"news_id": "42", "title": "Answer", "body_html": "<p>Body</p>"})
    index_path = tmp_path / "index.json"
    _write(
        index_path,
        {
            "articles": [
                {
                    "news_id": "42",
                    "title": "Answer",
                    "timestamp": "2025-01-01T00:00:00Z",
                    "article_path": str(article),
                }
            ]
        },
    )

    repo = NewsRepository(index_path=index_path)
    loaded = repo.get_article_by_news_id("42")
    assert loaded is not None
    assert loaded["title"] == "Answer"
