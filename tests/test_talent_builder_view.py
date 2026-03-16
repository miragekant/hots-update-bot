import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

import discord

from bot.talent_builder import TalentBuildData, TalentBuildHero, TalentBuildTier, TalentBuildTierOption
from bot.talent_builder_view import HERO_PAGE_SIZE, TALENT_ANY_VALUE, TalentBuilderHeroSelectView, TalentBuilderView, create_talent_builder_entry
from bot.pagination import HeroPaginationView
from bot.heroesprofile_repository import HeroesProfileRepository


class _FakeMessage:
    def __init__(self) -> None:
        self.edited = None

    async def edit(self, **kwargs) -> None:
        self.edited = kwargs


class _FakeResponse:
    def __init__(self) -> None:
        self.edited_embed = None
        self.edited_view = None
        self.sent_message = None
        self.sent_modal = None

    async def edit_message(self, *, embed, view) -> None:
        self.edited_embed = embed
        self.edited_view = view

    async def send_message(self, content=None, *, embed=None, view=None, ephemeral: bool) -> None:
        self.sent_message = {"content": content, "embed": embed, "view": view, "ephemeral": ephemeral}

    async def send_modal(self, modal) -> None:
        self.sent_modal = modal


class _FakeInteraction:
    def __init__(self, user_id: int) -> None:
        self.user = SimpleNamespace(id=user_id)
        self.response = _FakeResponse()

    async def original_response(self):
        return _FakeMessage()


class _Repo:
    def __init__(self, build_data: TalentBuildData, hero_count: int = 1) -> None:
        self.build_data = build_data
        self.hero_count = hero_count

    def list_talent_build_heroes(self):
        if self.hero_count == 1:
            return [self.build_data.hero]
        return [
            TalentBuildHero(slug=f"hero-{idx}", name=f"Hero {idx}", export_token=f"Hero{idx}")
            for idx in range(self.hero_count)
        ]

    def get_talent_build(self, hero_name_or_slug: str):
        if hero_name_or_slug in {self.build_data.hero.slug, self.build_data.hero.name}:
            return self.build_data
        return None


def _build_data() -> TalentBuildData:
    return TalentBuildData(
        hero=TalentBuildHero(slug="leoric", name="Leoric", export_token="Leoric"),
        tiers=[
            TalentBuildTier(
                level="1",
                options=[
                    TalentBuildTierOption(index=1, title="Consume Vitality", description="Range", hotkey="Q"),
                    TalentBuildTierOption(index=2, title="Fealty Unto Death", description="Sustain", hotkey="Trait"),
                ],
            ),
            TalentBuildTier(level="4", options=[TalentBuildTierOption(index=1, title="Ghastly Reach", hotkey="Q")]),
            TalentBuildTier(level="7", options=[TalentBuildTierOption(index=1, title="Willing Vessel", hotkey="W")]),
            TalentBuildTier(level="10", options=[]),
            TalentBuildTier(level="13", options=[]),
            TalentBuildTier(level="16", options=[]),
            TalentBuildTier(level="20", options=[]),
        ],
    )


def test_talent_builder_view_rejects_other_users():
    async def _run() -> None:
        view = TalentBuilderView(build_data=_build_data(), requesting_user_id=123)
        interaction = _FakeInteraction(user_id=456)

        allowed = await view.interaction_check(interaction)

        assert allowed is False
        assert interaction.response.sent_message == {
            "content": "Only the original requester can use these controls.",
            "embed": None,
            "view": None,
            "ephemeral": True,
        }

    asyncio.run(_run())


def test_talent_builder_view_changes_tier_and_marks_any_talent():
    async def _run() -> None:
        view = TalentBuilderView(build_data=_build_data(), requesting_user_id=123)
        interaction = _FakeInteraction(user_id=123)

        view.selections["1"] = 2
        tier_select = next(child for child in view.children if isinstance(child, discord.ui.Select) and "tier" in child.placeholder.lower())
        tier_select._values = ["4"]
        await tier_select.callback(interaction)
        assert view.active_level == "4"

        await view.any_button.callback(interaction)
        assert view.selections["4"] == TALENT_ANY_VALUE
        assert interaction.response.edited_embed.footer.text == "Talent Builder • Editing Level 4"

    asyncio.run(_run())


def test_talent_builder_view_selects_talent_and_finishes():
    async def _run() -> None:
        view = TalentBuilderView(build_data=_build_data(), requesting_user_id=123)
        message = _FakeMessage()
        view.set_message(message)
        interaction = _FakeInteraction(user_id=123)

        talent_select = next(child for child in view.children if isinstance(child, discord.ui.Select) and "Select Level" in child.placeholder)
        talent_select._values = ["2"]
        await talent_select.callback(interaction)
        assert view.selections["1"] == 2

        await view.finish_button.callback(interaction)
        assert interaction.response.sent_modal is not None

        modal_interaction = _FakeInteraction(user_id=123)
        await view.complete(modal_interaction, "Drain King")

        assert modal_interaction.response.sent_message["ephemeral"] is True
        assert modal_interaction.response.sent_message["embed"].title == "Leoric Build - Drain King"
        assert "Level 1: [2] Fealty Unto Death" in modal_interaction.response.sent_message["embed"].fields[0].value
        assert "[T2000000,Leoric]" in modal_interaction.response.sent_message["content"]
        assert message.edited["view"] is None

    asyncio.run(_run())


def test_talent_builder_hero_select_view_pages_and_starts_builder():
    async def _run() -> None:
        repo = _Repo(_build_data(), hero_count=HERO_PAGE_SIZE + 1)
        view = TalentBuilderHeroSelectView(repository=repo, requesting_user_id=123)
        view.set_message(_FakeMessage())
        interaction = _FakeInteraction(user_id=123)

        hero_select = next(child for child in view.children if isinstance(child, discord.ui.Select))
        assert len(hero_select.options) == HERO_PAGE_SIZE
        assert view.next_button.disabled is False

        await view.next_button.callback(interaction)
        assert view.page == 2

        await view.start_builder(interaction, "leoric")
        assert isinstance(interaction.response.edited_view, TalentBuilderView)
        assert interaction.response.edited_embed.title == "Talent Builder - Leoric"

    asyncio.run(_run())


def _write(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


def _repository_with_vikings(tmp_path: Path) -> HeroesProfileRepository:
    _write(
        tmp_path / "heroes" / "index.json",
        {
            "heroes": [
                {
                    "name": "The Lost Vikings",
                    "slug": "thelostvikings",
                    "short_name": "thelostvikings",
                    "build_copy_name": "LostVikings",
                    "file_path": str(tmp_path / "heroes" / "by_name" / "thelostvikings.json"),
                }
            ]
        },
    )
    _write(
        tmp_path / "heroes" / "by_name" / "thelostvikings.json",
        {
            "name": "The Lost Vikings",
            "slug": "thelostvikings",
            "build_copy_name": "LostVikings",
        },
    )
    _write(
        tmp_path / "talents" / "by_hero" / "thelostvikings.json",
        {
            "levels": ["1", "4", "7", "10", "13", "16", "20"],
            "talents_by_level": {
                "1": [{"title": "Olaf the Stout", "description": "Level 1 detail", "hotkey": "Passive"}],
                "4": [{"title": "Pain Don't Hurt", "description": "Level 4 detail", "hotkey": "Passive"}],
                "7": [{"title": "Spin To Win!", "description": "Level 7 detail", "hotkey": "W"}],
                "10": [{"title": "Longboat Raid!", "description": "Level 10 detail", "hotkey": "R"}],
                "13": [{"title": "Hunka' Burning Olaf", "description": "Level 13 detail", "hotkey": "Trait"}],
                "16": [{"title": "Large and In Charge", "description": "Level 16 detail", "hotkey": "Passive"}],
                "20": [{"title": "Checkpoint Reached", "description": "Level 20 detail", "hotkey": "Passive"}],
            },
        },
    )
    return HeroesProfileRepository(data_root=tmp_path)


def test_create_talent_builder_entry_parses_talent_string_into_paginated_result(tmp_path: Path):
    async def _run() -> None:
        interaction = _FakeInteraction(user_id=123)
        repo = _repository_with_vikings(tmp_path)

        await create_talent_builder_entry(
            interaction=interaction,
            repository=repo,
            requesting_user_id=123,
            hero_name=None,
            talent_string="[T1111111,LostVikings]",
        )

        sent = interaction.response.sent_message
        assert sent["ephemeral"] is True
        assert "[T1111111,LostVikings]" in sent["content"]
        assert sent["embed"].title == "The Lost Vikings Build"
        assert isinstance(sent["view"], HeroPaginationView)
        assert "Level 1: [1] **Olaf the Stout** `Passive`" in sent["embed"].fields[0].value
        assert [button.label for button in sent["view"].page_buttons] == [
            "Summary",
            "Level 1",
            "Level 4",
            "Level 7",
            "Level 10",
            "Level 13",
            "Level 16",
            "Level 20",
        ]

    asyncio.run(_run())


def test_parsed_talent_builder_tier_buttons_jump_to_requested_level(tmp_path: Path):
    async def _run() -> None:
        interaction = _FakeInteraction(user_id=123)
        repo = _repository_with_vikings(tmp_path)

        await create_talent_builder_entry(
            interaction=interaction,
            repository=repo,
            requesting_user_id=123,
            hero_name=None,
            talent_string="[T1111111,LostVikings]",
        )

        view = interaction.response.sent_message["view"]
        assert isinstance(view, HeroPaginationView)
        level_10_button = next(button for button in view.page_buttons if button.label == "Level 10")

        click_interaction = _FakeInteraction(user_id=123)
        await level_10_button.callback(click_interaction)

        assert click_interaction.response.edited_embed.title == "The Lost Vikings Build - Level 10"
        assert level_10_button.disabled is True

    asyncio.run(_run())


def test_create_talent_builder_entry_rejects_invalid_tier_index(tmp_path: Path):
    async def _run() -> None:
        interaction = _FakeInteraction(user_id=123)
        repo = _repository_with_vikings(tmp_path)

        await create_talent_builder_entry(
            interaction=interaction,
            repository=repo,
            requesting_user_id=123,
            hero_name=None,
            talent_string="[T2111111,LostVikings]",
        )

        assert interaction.response.sent_message["content"] == (
            "Talent string selects option `2` for Level 1, but `The Lost Vikings` only has 1 cached option(s) for that tier."
        )
        assert interaction.response.sent_message["ephemeral"] is True

    asyncio.run(_run())


def test_create_talent_builder_entry_rejects_hero_mismatch(tmp_path: Path):
    async def _run() -> None:
        interaction = _FakeInteraction(user_id=123)
        repo = _repository_with_vikings(tmp_path)

        await create_talent_builder_entry(
            interaction=interaction,
            repository=repo,
            requesting_user_id=123,
            hero_name="Unknown Hero",
            talent_string="[T1111111,LostVikings]",
        )

        assert interaction.response.sent_message["content"] == (
            "Hero talent data is not available in local cache. Run `python heroesprofile/update_data.py --only heroes,talents` first."
        )
        assert interaction.response.sent_message["ephemeral"] is True

    asyncio.run(_run())
