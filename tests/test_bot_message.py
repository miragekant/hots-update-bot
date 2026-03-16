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


def test_format_hero_list_embed_shows_summary_lines():
    embed = message.format_hero_list_embed(
        [{"name": "Abathur", "role": "Specialist", "new_role": "Support", "type": "Melee"}],
        page=1,
        total_pages=2,
    )
    assert embed.title == "HOTS Heroes"
    assert "Abathur" in embed.fields[0].value
    assert "Support" in embed.fields[0].value
    assert embed.footer.text == "Page 1/2"


def test_format_map_list_embed_shows_flags():
    embed = message.format_map_list_embed(
        [{"name": "Alterac Pass", "type": "standard", "playable": 1, "ranked_rotation": 0}],
        page=2,
        total_pages=3,
    )
    assert embed.title == "HOTS Maps"
    assert "Playable" in embed.fields[0].value
    assert "Not ranked" in embed.fields[0].value
    assert embed.footer.text == "Page 2/3"


def test_format_patch_list_embed_shows_latest_build():
    embed = message.format_patch_list_embed(
        [{"version_family": "2.55", "build_count": 2, "builds": ["2.55.15.96477", "2.55.14.95918"]}],
        page=1,
        total_pages=1,
    )
    assert embed.title == "HOTS Patches"
    assert "2.55" in embed.fields[0].value
    assert "2 builds" in embed.fields[0].value
    assert "2.55.15.96477" in embed.fields[0].value


def test_format_article_body_embed_pages_has_fallback():
    pages = message.format_article_body_embed_pages({"body_html": ""})
    assert pages == ["_No article body available._"]


def test_format_article_body_embed_pages_respects_limit():
    article = {"body_html": "<p>" + ("z " * 5000) + "</p>"}
    pages = message.format_article_body_embed_pages(article, max_chars=300)
    assert len(pages) > 1
    assert all(len(page) <= 300 for page in pages)


def test_format_hero_embeds_includes_summary_and_talent_pages():
    hero = {
        "name": "Abathur",
        "role": "Specialist",
        "new_role": "Support",
        "type": "Melee",
        "release_date": "2014-03-13 00:00:01",
        "last_change_patch_version": "2.55.4.91769",
        "aliases": ["Abathur", "абатур"],
    }
    talents = {
        "levels": ["1"],
        "talents_by_level": {
            "1": [
                {"title": "Pressurized Glands", "description": "Increase range.", "hotkey": "W"},
                {"title": "Reinforced Carapace", "description": "Increase shield.", "hotkey": "E"},
            ]
        },
    }

    embeds = message.format_hero_embeds(hero, talents)
    assert embeds[0].title == "Abathur"
    assert embeds[1].title == "Abathur Talents - Level 1"
    assert "Pressurized Glands" in (embeds[1].description or "")


def test_format_hero_pages_returns_verbose_targets_for_overflow():
    hero = {
        "name": "Abathur",
        "role": "Specialist",
        "new_role": "Support",
        "type": "Melee",
    }
    talents = {
        "levels": ["1", "4"],
        "talents_by_level": {
            "1": [
                {"title": "Talent A", "description": ("alpha " * 1200).strip(), "hotkey": "Q"},
                {"title": "Talent B", "description": ("beta " * 1200).strip(), "hotkey": "W"},
            ],
            "4": [{"title": "Talent C", "description": "Short description.", "hotkey": "E"}],
        },
    }

    embeds, page_targets = message.format_hero_pages(hero, talents)

    assert embeds[0].footer.text == "HeroesProfile • Summary"
    assert page_targets[0].label == "Summary"
    assert page_targets[1].label.startswith("Level 1 (1/")
    assert any(target.label.startswith("Level 1 (2/") for target in page_targets)
    assert page_targets[-1].label == "Level 4"
    assert page_targets[-1].page_index == len(embeds) - 1


def test_format_patch_embeds_marks_matched_build():
    embeds = message.format_patch_embeds(
        {
            "version_family": "2.55",
            "builds": ["2.55.15.96477", "2.55.14.95918"],
            "matched_build": "2.55.15.96477",
        }
    )
    assert embeds[0].title == "Patch 2.55"
    assert "2.55.15.96477" in (embeds[0].description or "")
    assert any(field.name == "Matched Build" for field in embeds[0].fields)
