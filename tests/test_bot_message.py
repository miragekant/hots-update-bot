from bot import message


def test_split_text_chunks_respects_max_chars():
    text = "## Title\n\nParagraph one.\n\n" + ("word " * 600)
    chunks = message.split_markdown_chunks(text, max_chars=200)
    assert len(chunks) > 1
    assert all(len(chunk) <= 200 for chunk in chunks)


def test_render_preserves_headings_and_paragraphs():
    html = "<h2>Patch Notes</h2><p>Balance updates shipped.</p>"
    rendered = message.render_html_to_discord_markdown(html)
    assert "## Patch Notes" in rendered
    assert "Balance updates shipped." in rendered


def test_render_preserves_nested_lists_compactly():
    html = """
    <ul>
      <li>Top
        <ul>
          <li>Child</li>
        </ul>
      </li>
    </ul>
    """
    rendered = message.render_html_to_discord_markdown(html)
    assert "- Top" in rendered
    assert "  - Child" in rendered


def test_render_converts_links_to_markdown():
    html = '<p>Hello <a href="https://example.com/x">world</a></p>'
    rendered = message.render_html_to_discord_markdown(html)
    assert "[world](https://example.com/x)" in rendered


def test_render_handles_blockquote_and_emphasis():
    html = "<blockquote><p><strong>Important</strong> and <em>urgent</em></p></blockquote>"
    rendered = message.render_html_to_discord_markdown(html)
    assert "> **Important** and *urgent*" in rendered


def test_render_handles_code_blocks():
    html = "<pre><code>line_a\nline_b</code></pre>"
    rendered = message.render_html_to_discord_markdown(html)
    assert "```" in rendered
    assert "line_a" in rendered
    assert "line_b" in rendered


def test_chunker_keeps_nonempty_chunks():
    html = "<h2>Header</h2><p>" + ("x" * 3000) + "</p>"
    rendered = message.render_html_to_discord_markdown(html)
    chunks = message.split_markdown_chunks(rendered, max_chars=300)
    assert len(chunks) > 1
    assert all(chunk.strip() for chunk in chunks)
    assert all(len(chunk) <= 300 for chunk in chunks)


def test_compact_mode_is_shorter_than_noncompact():
    html = "<h2>A</h2><p>P1</p><p>P2</p><ul><li>x</li><li>y</li></ul>"
    compact = message.render_html_to_discord_markdown(html, compact=True)
    noncompact = message.render_html_to_discord_markdown(html, compact=False)
    assert len(compact) < len(noncompact)


def test_format_news_list_embed_has_paging_footer():
    items = [{"title": "A", "timestamp": "2025-01-01T00:00:00Z"}, {"title": "B", "timestamp": "2025-01-02T00:00:00Z"}]
    embed = message.format_news_list_embed(items, page=1, total_pages=3, year_filter=2025)
    assert embed.title == "HOTS News (2025)"
    assert embed.footer.text == "Page 1/3"


def test_format_article_body_embed_pages_has_fallback():
    pages = message.format_article_body_embed_pages({"body_html": ""})
    assert pages == ["_No article body available._"]


def test_format_article_body_embed_pages_respects_limit():
    article = {"body_html": "<p>" + ("z " * 5000) + "</p>"}
    pages = message.format_article_body_embed_pages(article, max_chars=300)
    assert len(pages) > 1
    assert all(len(page) <= 300 for page in pages)
