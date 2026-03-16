import asyncio
from types import SimpleNamespace

import discord

from bot.message import HeroPageTarget
from bot.pagination import (
    ArticlePaginationView,
    EmbedPaginationView,
    HeroPaginationView,
    HeroesProfileListPaginationView,
    build_article_page_embed,
    compute_total_pages,
    page_slice,
)


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


def test_embed_pagination_view_button_state():
    async def _run() -> None:
        embeds = [discord.Embed(title="One"), discord.Embed(title="Two")]
        view = EmbedPaginationView(embeds=embeds, requesting_user_id=123)
        assert view.prev_button.disabled is True
        assert view.next_button.disabled is False
        assert view.current_embed().title == "One"

        view.page = 2
        view._refresh_components()
        assert view.prev_button.disabled is False
        assert view.next_button.disabled is True
        assert view.current_embed().title == "Two"

    asyncio.run(_run())


class _FakeResponse:
    def __init__(self) -> None:
        self.edited_embed = None
        self.edited_view = None
        self.sent_message = None

    async def edit_message(self, *, embed, view) -> None:
        self.edited_embed = embed
        self.edited_view = view

    async def send_message(self, content: str | None = None, *, ephemeral: bool = False, embed=None, view=None) -> None:
        self.sent_message = {"content": content, "ephemeral": ephemeral, "embed": embed, "view": view}


class _FakeInteraction:
    def __init__(self, user_id: int) -> None:
        self.user = SimpleNamespace(id=user_id)
        self.response = _FakeResponse()


def test_hero_pagination_view_switches_pages_and_disables_active_button():
    async def _run() -> None:
        embeds = [
            discord.Embed(title="Summary"),
            discord.Embed(title="Level 1"),
            discord.Embed(title="Level 4"),
        ]
        page_targets = [
            HeroPageTarget(label="Summary", page_index=0),
            HeroPageTarget(label="Level 1", page_index=1),
            HeroPageTarget(label="Level 4", page_index=2),
        ]
        view = HeroPaginationView(embeds=embeds, page_targets=page_targets, requesting_user_id=123)

        assert view.page_buttons[0].disabled is True
        assert view.page_buttons[1].disabled is False
        assert view.current_embed().title == "Summary"

        interaction = _FakeInteraction(user_id=123)
        await view.page_buttons[1].callback(interaction)

        assert view.current_embed().title == "Level 1"
        assert interaction.response.edited_embed.title == "Level 1"
        assert view.page_buttons[0].disabled is False
        assert view.page_buttons[1].disabled is True

    asyncio.run(_run())


def test_hero_pagination_view_supports_summary_and_tier_buttons():
    async def _run() -> None:
        embeds = [discord.Embed(title="Summary"), discord.Embed(title="Level 1"), discord.Embed(title="Level 4")]
        page_targets = [
            HeroPageTarget(label="Summary", page_index=0),
            HeroPageTarget(label="Level 1", page_index=1),
            HeroPageTarget(label="Level 4", page_index=2),
        ]
        view = HeroPaginationView(embeds=embeds, page_targets=page_targets, requesting_user_id=123)

        assert [button.label for button in view.page_buttons] == ["Summary", "Level 1", "Level 4"]

    asyncio.run(_run())


def test_hero_pagination_view_rejects_other_users():
    async def _run() -> None:
        view = HeroPaginationView(
            embeds=[discord.Embed(title="Summary")],
            page_targets=[HeroPageTarget(label="Summary", page_index=0)],
            requesting_user_id=123,
        )
        interaction = _FakeInteraction(user_id=456)

        allowed = await view.interaction_check(interaction)

        assert allowed is False
        assert interaction.response.sent_message == {
            "content": "Only the original requester can use these controls.",
            "ephemeral": True,
            "embed": None,
            "view": None,
        }

    asyncio.run(_run())


def test_heroesprofile_list_pagination_view_pages_and_selects_detail():
    async def _run() -> None:
        items = [{"slug": f"hero-{index}", "name": f"Hero {index}", "role": "Support"} for index in range(12)]
        view = HeroesProfileListPaginationView(
            requesting_user_id=123,
            items=items,
            page_size=10,
            select_placeholder="Select a hero to open",
            embed_builder=lambda current, page, total: discord.Embed(title=f"Page {page}/{total}", description=str(len(current))),
            option_label_getter=lambda item: item["name"],
            option_description_getter=lambda item: item["role"],
            option_value_getter=lambda item: item["slug"],
            detail_loader=lambda selected: (discord.Embed(title=selected), None),
        )

        assert view.prev_button.disabled is True
        assert view.next_button.disabled is False
        assert [option.value for option in view.select.options] == [f"hero-{index}" for index in range(10)]

        interaction = _FakeInteraction(user_id=123)
        await view.next_button.callback(interaction)
        assert interaction.response.edited_embed.title == "Page 2/2"
        assert [option.value for option in view.select.options] == ["hero-10", "hero-11"]

        view.select._values = ["hero-10"]
        select_interaction = _FakeInteraction(user_id=123)
        await view.select.callback(select_interaction)
        assert select_interaction.response.sent_message["embed"].title == "hero-10"
        assert select_interaction.response.sent_message["view"] is None

    asyncio.run(_run())


def test_heroesprofile_list_pagination_view_rejects_other_users():
    async def _run() -> None:
        view = HeroesProfileListPaginationView(
            requesting_user_id=123,
            items=[{"slug": "hero-1", "name": "Hero 1"}],
            page_size=10,
            select_placeholder="Select a hero to open",
            embed_builder=lambda current, page, total: discord.Embed(title="Heroes"),
            option_label_getter=lambda item: item["name"],
            option_description_getter=lambda item: "Role",
            option_value_getter=lambda item: item["slug"],
            detail_loader=lambda selected: (discord.Embed(title=selected), None),
        )
        interaction = _FakeInteraction(user_id=456)

        allowed = await view.interaction_check(interaction)

        assert allowed is False
        assert interaction.response.sent_message == {
            "content": "Only the original requester can use these controls.",
            "ephemeral": True,
            "embed": None,
            "view": None,
        }

    asyncio.run(_run())


def test_heroesprofile_list_pagination_view_reports_missing_detail():
    async def _run() -> None:
        view = HeroesProfileListPaginationView(
            requesting_user_id=123,
            items=[{"slug": "hero-1", "name": "Hero 1"}],
            page_size=10,
            select_placeholder="Select a hero to open",
            embed_builder=lambda current, page, total: discord.Embed(title="Heroes"),
            option_label_getter=lambda item: item["name"],
            option_description_getter=lambda item: "Role",
            option_value_getter=lambda item: item["slug"],
            detail_loader=lambda selected: None,
        )

        view.select._values = ["hero-1"]
        interaction = _FakeInteraction(user_id=123)
        await view.select.callback(interaction)

        assert interaction.response.sent_message == {
            "content": "Item is not available in local cache.",
            "ephemeral": True,
            "embed": None,
            "view": None,
        }

    asyncio.run(_run())
