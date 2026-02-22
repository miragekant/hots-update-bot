from pathlib import Path

import news.update_news as upd


FEED_HTML = """
<html><body>
  <blz-news-featured-cards class="section-featured-news">
    <blz-news class="featured-news">
      <blz-news-card href="/en-us/article/1001/first-featured">
        <h1 slot="heading">First Featured</h1>
        <p slot="description">Desc A</p>
        <blz-timestamp slot="metadata" timestamp="2025-09-30T10:00:00Z"></blz-timestamp>
        <blz-image slot="image" src="/img/a.png"></blz-image>
      </blz-news-card>
    </blz-news>
  </blz-news-featured-cards>

  <div class="LatestNews">
    <section class="LatestNews-feed">
      <blz-news-feed>
        <ol class="card-list">
          <li>
            <blz-news-card href="/en-us/article/1001/first-featured">
              <h1 slot="heading">Duplicate In Latest</h1>
              <blz-timestamp slot="metadata" timestamp="2025-09-30T10:00:00Z"></blz-timestamp>
            </blz-news-card>
          </li>
          <li>
            <blz-news-card href="/en-us/article/1002/second-latest">
              <h1 slot="heading">Second Latest</h1>
              <p slot="description">Desc B</p>
              <blz-timestamp slot="metadata" timestamp="2025-09-29T09:00:00Z"></blz-timestamp>
              <blz-image slot="image" src="https://cdn.example.com/b.png"></blz-image>
            </blz-news-card>
          </li>
        </ol>
      </blz-news-feed>
    </section>
  </div>
</body></html>
"""

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


def test_parse_feed_extracts_featured_and_latest_cards_and_dedupes():
    items = upd.parse_feed(FEED_HTML, base_url="https://news.blizzard.com/en-us/feed/heroes-of-the-storm")
    assert [item.news_id for item in items] == ["1001", "1002"]
    assert items[0].section == "featured"
    assert items[1].section == "latest"
    assert items[0].title == "First Featured"
    assert items[1].image_url == "https://cdn.example.com/b.png"


def test_parse_article_extracts_metadata_and_preserves_structure_with_normalized_urls():
    detail = upd.parse_article(
        ARTICLE_HTML,
        "https://news.blizzard.com/en-us/article/1001/first-featured",
    )

    assert detail.author == "Blizzard Entertainment"
    assert detail.published_at == "2025-09-30T17:11:00Z"
    assert detail.header_image_url == "https://news.blizzard.com/hero/header.png"

    # Structure should remain (headings/lists/nested lists) and relative URLs normalized.
    assert "<h2>Quick Navigation</h2>" in detail.body_html
    assert "<ul>" in detail.body_html
    assert "Nested" in detail.body_html
    assert 'href="https://news.blizzard.com/relative/page"' in detail.body_html
    assert 'src="https://news.blizzard.com/media/asset.png"' in detail.body_html


def test_merge_updates_orders_by_timestamp_desc():
    index = {
        "generated_at": None,
        "count": 1,
        "articles": [
            {
                "news_id": "1001",
                "url": "u1",
                "title": "A",
                "timestamp": "2025-01-01T00:00:00Z",
                "updated_at": "2025-01-01T00:00:00Z",
                "section": "featured",
                "article_path": "news/articles/1001.json",
            }
        ],
    }
    merged = upd.merge_updates(
        index,
        [
            {
                "news_id": "1002",
                "url": "u2",
                "title": "B",
                "timestamp": "2025-02-01T00:00:00Z",
                "updated_at": "2025-02-01T00:00:00Z",
                "section": "latest",
                "article_path": "news/articles/1002.json",
            }
        ],
    )

    assert [a["news_id"] for a in merged["articles"]] == ["1002", "1001"]


def test_update_news_incremental_skips_unchanged_and_updates_changed(monkeypatch, tmp_path: Path):
    index_path = tmp_path / "index.json"
    article_dir = tmp_path / "articles"

    existing = {
        "generated_at": None,
        "count": 1,
        "articles": [
            {
                "news_id": "1001",
                "url": "https://news.blizzard.com/en-us/article/1001/first-featured",
                "title": "First Featured",
                "timestamp": "2025-09-30T10:00:00Z",
                "updated_at": "2025-09-30T10:00:00Z",
                "section": "featured",
                "article_path": "news/articles/1001.json",
            }
        ],
    }
    upd.write_index(existing, index_path)

    feed = [
        upd.ArticleMeta(
            news_id="1001",
            url="https://news.blizzard.com/en-us/article/1001/first-featured",
            title="First Featured",
            description="A",
            section="featured",
            timestamp="2025-09-30T10:00:00Z",
            image_url=None,
        ),
        upd.ArticleMeta(
            news_id="1002",
            url="https://news.blizzard.com/en-us/article/1002/second-latest",
            title="Second Latest",
            description="B",
            section="latest",
            timestamp="2025-10-01T10:00:00Z",
            image_url=None,
        ),
    ]

    monkeypatch.setattr(upd, "fetch_feed_html", lambda: "ignored")
    monkeypatch.setattr(upd, "parse_feed", lambda *_args, **_kwargs: feed)
    monkeypatch.setattr(upd, "fetch_article_html", lambda _url: ARTICLE_HTML)

    stats = upd.update_news(index_path=index_path, article_dir=article_dir)

    assert stats.unchanged == 1
    assert stats.new == 1
    assert stats.updated == 0
    assert stats.failed == 0

    saved_article = article_dir / "1002.json"
    assert saved_article.exists()

    saved_index = upd.load_index(index_path)
    assert saved_index["count"] == 2
    assert saved_index["articles"][0]["news_id"] == "1002"
