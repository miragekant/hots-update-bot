import asyncio

from bot.pagination import ArticlePaginationView, build_article_page_embed, compute_total_pages, page_slice


def test_compute_total_pages():
    assert compute_total_pages(0, 5) == 1
    assert compute_total_pages(5, 5) == 1
    assert compute_total_pages(6, 5) == 2


def test_page_slice():
    items = [{"id": str(i)} for i in range(12)]
    first = page_slice(items, page=1, page_size=5)
    third = page_slice(items, page=3, page_size=5)
    assert len(first) == 5
    assert [x["id"] for x in third] == ["10", "11"]


def test_article_pagination_view_button_state_and_embed_footer():
    async def _run() -> None:
        article = {"title": "Patch Notes", "description": "Summary", "url": "https://example.com/a", "body_html": "<p>x</p>"}
        view = ArticlePaginationView(article=article, requesting_user_id=123, page_chunks=["page1", "page2"])
        assert view.prev_button.disabled is True
        assert view.next_button.disabled is False
        assert view.current_embed().footer.text == "Page 1/2"

        view.page = 2
        view._refresh_components()
        assert view.prev_button.disabled is False
        assert view.next_button.disabled is True
        assert view.current_embed().footer.text == "Page 2/2"

    asyncio.run(_run())


def test_build_article_page_embed_uses_page_text():
    article = {"title": "T", "description": "Summary", "url": "https://example.com", "body_html": "<p>body</p>"}
    embed = build_article_page_embed(article, "Body page content", page=1, total_pages=3)
    assert embed.description == "Body page content"
    assert embed.footer.text == "Page 1/3"
