from datetime import datetime, timedelta, timezone
from pathlib import Path

import news.update_news as upd


ARTICLE_HTML = """
<html><body>
  <article class="Content theme-bg">
    <header class="ContentHeader">
      <div class="details">
        <div class="author">Blizzard Entertainment</div>
      </div>
      <blz-timestamp timestamp="2025-09-30T17:11:00Z"></blz-timestamp>
      <blz-image src="/hero/header.png"></blz-image>
    </header>
    <section class="blog">
      <h2>Quick Navigation</h2>
      <ul><li><a href="#General">General</a></li></ul>
      <p><a href="/relative/page">relative</a></p>
      <p><img src="/media/asset.png" alt="asset"></p>
      <ul>
        <li>Top
          <ul>
            <li>Nested</li>
          </ul>
        </li>
      </ul>
    </section>
  </article>
</body></html>
"""


def make_group(news_id: str, title: str, ts: str, path: str | None = None) -> dict:
    return {
        "properties": {
            "newsPath": path or f"/en-us/article/{news_id}/{title.lower().replace(' ', '-')}",
            "title": title,
            "summary": f"Summary {news_id}",
            "lastUpdated": ts,
            "staticAsset": {"imageUrl": f"https://cdn.example.com/{news_id}.png"},
        }
    }


def test_discover_all_article_meta_extracts_and_dedupes(monkeypatch):
    root = {
        "sections": [{"name": "Featured", "contentGroups": [make_group("1001", "Featured A", "2025-09-30T10:00:00Z")]}],
        "feed": {
            "contentItems": [
                make_group("1001", "Duplicate Featured", "2025-09-30T10:00:00Z"),
                make_group("1002", "Latest B", "2025-09-29T09:00:00Z"),
            ],
            "pagination": {"offset": 0, "limit": 2, "hasNextPage": True},
        },
    }
    page2 = {
        "contentItems": [make_group("1003", "Older C", "2025-09-28T08:00:00Z")],
        "pagination": {"offset": 2, "limit": 2, "hasNextPage": False},
    }

    monkeypatch.setattr(upd, "fetch_news_api_json", lambda: root)
    monkeypatch.setattr(upd, "fetch_feed_page_json", lambda offset=0, filters=None: page2)

    items = upd.discover_all_article_meta()
    assert [i.news_id for i in items] == ["1001", "1002", "1003"]
    assert items[0].section == "featured"
    assert items[1].section == "latest"


def test_discover_stops_pagination_early_when_out_of_range(monkeypatch):
    root = {
        "sections": [],
        "feed": {
            "contentItems": [make_group("1001", "Recent A", "2026-01-01T00:00:00Z")],
            "pagination": {"offset": 0, "limit": 1, "hasNextPage": True},
        },
    }
    calls: list[int] = []

    def fake_page(offset=0, filters=None):
        calls.append(offset)
        return {
            "contentItems": [make_group("0900", "Old B", "2024-01-01T00:00:00Z")],
            "pagination": {"offset": offset, "limit": 1, "hasNextPage": True},
        }

    monkeypatch.setattr(upd, "fetch_news_api_json", lambda: root)
    monkeypatch.setattr(upd, "fetch_feed_page_json", fake_page)

    start_dt = datetime(2025, 11, 1, tzinfo=timezone.utc)
    items = upd.discover_all_article_meta(start_dt=start_dt)
    assert [i.news_id for i in items] == ["1001", "0900"]
    assert calls == [1]


def test_parse_article_extracts_metadata_and_preserves_structure_with_normalized_urls():
    detail = upd.parse_article(
        ARTICLE_HTML,
        "https://news.blizzard.com/en-us/article/1001/first-featured",
    )

    assert detail.author == "Blizzard Entertainment"
    assert detail.published_at == "2025-09-30T17:11:00Z"
    assert detail.header_image_url == "https://news.blizzard.com/hero/header.png"
    assert "<h2>Quick Navigation</h2>" in detail.body_html
    assert "Nested" in detail.body_html
    assert 'href="https://news.blizzard.com/relative/page"' in detail.body_html
    assert 'src="https://news.blizzard.com/media/asset.png"' in detail.body_html


def test_compute_date_window_defaults_to_3_months():
    start, end = upd.compute_date_window(months=3)
    delta = end - start
    assert timedelta(days=89) <= delta <= timedelta(days=91)


def test_filter_meta_by_date_range_respects_window():
    start = datetime(2025, 9, 1, tzinfo=timezone.utc)
    end = datetime(2025, 9, 30, 23, 59, tzinfo=timezone.utc)

    items = [
        upd.ArticleMeta("1", "u1", "t1", "", "latest", "2025-09-15T00:00:00Z", None),
        upd.ArticleMeta("2", "u2", "t2", "", "latest", "2025-08-15T00:00:00Z", None),
        upd.ArticleMeta("3", "u3", "t3", "", "latest", None, None),
    ]

    filtered = upd.filter_meta_by_date_range(items, start, end)
    assert [i.news_id for i in filtered] == ["1"]


def test_write_article_uses_yyyy_mm_dd_path(tmp_path: Path):
    record = upd.ArticleRecord(
        news_id="1001",
        url="u",
        title="t",
        description="d",
        section="latest",
        timestamp="2025-09-30T17:11:00Z",
        image_url=None,
        author=None,
        published_at=None,
        updated_at="2025-09-30T17:11:00Z",
        header_image_url=None,
        body_html="<p>x</p>",
        fetched_at="2025-09-30T17:11:00Z",
        content_hash="h",
    )

    path = upd.write_article(record, tmp_path)
    assert path.as_posix().endswith("/2025/09/30/1001.json")


def test_update_news_logs_summary_and_stores_chronological_paths(monkeypatch, tmp_path: Path, capsys):
    upd.configure_logging()

    index_path = tmp_path / "index.json"
    article_dir = tmp_path / "articles"

    candidates = [
        upd.ArticleMeta(
            news_id="0900",
            url="https://news.blizzard.com/en-us/article/0900/older-missing",
            title="Older Missing",
            description="",
            section="latest",
            timestamp="2024-01-01T10:00:00Z",
            image_url=None,
        ),
    ]

    monkeypatch.setattr(upd, "discover_all_article_meta", lambda start_dt=None: candidates)
    monkeypatch.setattr(upd, "fetch_article_html", lambda _url: ARTICLE_HTML)

    start = datetime(2023, 1, 1, tzinfo=timezone.utc)
    end = datetime(2025, 12, 31, tzinfo=timezone.utc)

    stats = upd.update_news(index_path=index_path, article_dir=article_dir, start_dt=start, end_dt=end)
    assert stats.new == 1

    out = capsys.readouterr().out
    assert "starting update" in out
    assert "update finished" in out

    saved_index = upd.load_index(index_path)
    by_id = {item["news_id"]: item for item in saved_index["articles"]}
    assert "/2024/01/01/0900.json" in by_id["0900"]["article_path"]
