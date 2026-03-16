from __future__ import annotations

import discord

from bot.heroesprofile_repository import AmbiguousTalentBuildHeroError, HeroesProfileRepository
from bot.message import TalentBuilderTierOption, format_parsed_talent_build_embeds, format_talent_builder_embed, format_talent_build_result
from bot.pagination import HeroPaginationView
from bot.talent_builder import TALENT_LEVELS, TalentBuildData

HERO_PAGE_SIZE = 25
TALENT_ANY_VALUE = 0


def _tier_option_map(build_data: TalentBuildData) -> dict[str, list[TalentBuilderTierOption]]:
    return {
        tier.level: [
            TalentBuilderTierOption(
                index=option.index,
                title=option.title,
                description=option.description,
                hotkey=option.hotkey,
            )
            for option in tier.options
        ]
        for tier in build_data.tiers
    }


class TalentBuilderNameModal(discord.ui.Modal):
    def __init__(self, builder_view: "TalentBuilderView") -> None:
        super().__init__(title="Name Build")
        self.builder_view = builder_view
        self.build_name = discord.ui.TextInput(
            label="Build Name (optional)",
            required=False,
            max_length=80,
            placeholder="Drain Tank, Teamfight, Macro, etc.",
        )
        self.add_item(self.build_name)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await self.builder_view.complete(interaction, str(self.build_name.value or "").strip() or None)


class TalentBuilderTierSelect(discord.ui.Select["TalentBuilderView"]):
    def __init__(self, active_level: str) -> None:
        options = [
            discord.SelectOption(label=f"Level {level}", value=level, default=level == active_level) for level in TALENT_LEVELS
        ]
        super().__init__(placeholder="Choose a tier to edit", options=options, row=0)

    async def callback(self, interaction: discord.Interaction) -> None:
        assert self.view is not None
        self.view.active_level = self.values[0]
        self.view.refresh_components()
        await interaction.response.edit_message(embed=self.view.current_embed(), view=self.view)


class TalentBuilderTalentSelect(discord.ui.Select["TalentBuilderView"]):
    def __init__(self, *, active_level: str, tier_options: list[TalentBuilderTierOption]) -> None:
        options = [
            discord.SelectOption(
                label=option.title[:100],
                value=str(option.index),
                description=((f"{option.hotkey} - " if option.hotkey else "") + option.description)[:100] or None,
            )
            for option in tier_options
        ]
        if not options:
            options = [discord.SelectOption(label="No talents available", value="__none__", description="No local data")]
        super().__init__(placeholder=f"Select Level {active_level} talent", options=options, row=1)
        self.disabled = options[0].value == "__none__"

    async def callback(self, interaction: discord.Interaction) -> None:
        assert self.view is not None
        if self.values[0] == "__none__":
            await interaction.response.send_message("No local talents are available for this tier.", ephemeral=True)
            return
        self.view.selections[self.view.active_level] = int(self.values[0])
        self.view.refresh_components()
        await interaction.response.edit_message(embed=self.view.current_embed(), view=self.view)


class TalentBuilderView(discord.ui.View):
    def __init__(self, *, build_data: TalentBuildData, requesting_user_id: int, timeout: float = 300) -> None:
        super().__init__(timeout=timeout)
        self.build_data = build_data
        self.requesting_user_id = requesting_user_id
        self.active_level = TALENT_LEVELS[0]
        self.selections: dict[str, int] = {level: TALENT_ANY_VALUE for level in TALENT_LEVELS}
        self.message: discord.InteractionMessage | None = None
        self._tier_options = _tier_option_map(build_data)

        self.any_button = discord.ui.Button(label="Any Talent", style=discord.ButtonStyle.secondary, row=2)
        self.finish_button = discord.ui.Button(label="Finish", style=discord.ButtonStyle.success, row=2)
        self.cancel_button = discord.ui.Button(label="Cancel", style=discord.ButtonStyle.danger, row=2)
        self.any_button.callback = self._on_any_talent
        self.finish_button.callback = self._on_finish
        self.cancel_button.callback = self._on_cancel

        self.refresh_components()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == self.requesting_user_id:
            return True
        await interaction.response.send_message("Only the original requester can use these controls.", ephemeral=True)
        return False

    def set_message(self, message: discord.InteractionMessage) -> None:
        self.message = message

    def current_embed(self) -> discord.Embed:
        return format_talent_builder_embed(
            hero_name=self.build_data.hero.name,
            selections=self.selections,
            tier_options=self._tier_options,
            active_level=self.active_level,
        )

    def refresh_components(self) -> None:
        self.clear_items()
        self.add_item(TalentBuilderTierSelect(self.active_level))
        self.add_item(TalentBuilderTalentSelect(active_level=self.active_level, tier_options=self._tier_options.get(self.active_level) or []))
        self.add_item(self.any_button)
        self.add_item(self.finish_button)
        self.add_item(self.cancel_button)

    async def _on_any_talent(self, interaction: discord.Interaction) -> None:
        self.selections[self.active_level] = TALENT_ANY_VALUE
        self.refresh_components()
        await interaction.response.edit_message(embed=self.current_embed(), view=self)

    async def _on_finish(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_modal(TalentBuilderNameModal(self))

    async def _on_cancel(self, interaction: discord.Interaction) -> None:
        self.stop()
        await interaction.response.edit_message(
            embed=discord.Embed(title="Talent Builder Canceled", description="Start `/talentbuilder` again to make a new build."),
            view=None,
        )

    async def complete(self, interaction: discord.Interaction, build_name: str | None) -> None:
        from bot.talent_builder import build_talent_string

        talent_string = build_talent_string(self.build_data.hero.export_token, self.selections)
        embed, code_block = format_talent_build_result(
            hero_name=self.build_data.hero.name,
            build_name=build_name,
            talent_string=talent_string,
            selections=self.selections,
            tier_options=self._tier_options,
        )
        self.stop()
        await interaction.response.send_message(embed=embed, content=code_block, ephemeral=True)
        if self.message is not None:
            await self.message.edit(
                embed=discord.Embed(title="Talent Builder Closed", description="The exported build was posted in a separate ephemeral message."),
                view=None,
                content=None,
            )


class TalentBuilderHeroSelect(discord.ui.Select["TalentBuilderHeroSelectView"]):
    def __init__(self, *, heroes: list[dict[str, str]], page: int, total_pages: int) -> None:
        options = [
            discord.SelectOption(label=hero["name"][:100], value=hero["slug"], description=f"Export token: {hero['export_token']}"[:100])
            for hero in heroes
        ]
        if not options:
            options = [discord.SelectOption(label="No heroes available", value="__none__", description="No local talent cache")]
        super().__init__(placeholder=f"Select a hero ({page}/{total_pages})", options=options, row=0)
        self.disabled = options[0].value == "__none__"

    async def callback(self, interaction: discord.Interaction) -> None:
        assert self.view is not None
        await self.view.start_builder(interaction, self.values[0])


class TalentBuilderHeroSelectView(discord.ui.View):
    def __init__(self, *, repository: HeroesProfileRepository, requesting_user_id: int, timeout: float = 300) -> None:
        super().__init__(timeout=timeout)
        self.repository = repository
        self.requesting_user_id = requesting_user_id
        self.heroes = [
            {"name": hero.name, "slug": hero.slug, "export_token": hero.export_token} for hero in repository.list_talent_build_heroes()
        ]
        self.page = 1
        self.page_size = HERO_PAGE_SIZE
        self.total_pages = max(1, (len(self.heroes) + self.page_size - 1) // self.page_size)
        self.message: discord.InteractionMessage | None = None

        self.prev_button = discord.ui.Button(label="Prev", style=discord.ButtonStyle.secondary, row=1)
        self.next_button = discord.ui.Button(label="Next", style=discord.ButtonStyle.secondary, row=1)
        self.cancel_button = discord.ui.Button(label="Cancel", style=discord.ButtonStyle.danger, row=1)
        self.prev_button.callback = self._on_prev
        self.next_button.callback = self._on_next
        self.cancel_button.callback = self._on_cancel
        self.refresh_components()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == self.requesting_user_id:
            return True
        await interaction.response.send_message("Only the original requester can use these controls.", ephemeral=True)
        return False

    def set_message(self, message: discord.InteractionMessage) -> None:
        self.message = message

    def _current_items(self) -> list[dict[str, str]]:
        start = (self.page - 1) * self.page_size
        return self.heroes[start : start + self.page_size]

    def current_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title="Talent Builder",
            description="Select the hero you want to build from the local HeroesProfile cache.",
        )
        names = [f"{idx}. {hero['name']}" for idx, hero in enumerate(self._current_items(), start=1 + (self.page - 1) * self.page_size)]
        embed.add_field(name="Heroes", value="\n".join(names) if names else "No eligible heroes found.", inline=False)
        embed.set_footer(text=f"Page {self.page}/{self.total_pages}")
        return embed

    def refresh_components(self) -> None:
        self.clear_items()
        self.add_item(TalentBuilderHeroSelect(heroes=self._current_items(), page=self.page, total_pages=self.total_pages))
        self.prev_button.disabled = self.page <= 1
        self.next_button.disabled = self.page >= self.total_pages
        self.add_item(self.prev_button)
        self.add_item(self.next_button)
        self.add_item(self.cancel_button)

    async def _on_prev(self, interaction: discord.Interaction) -> None:
        self.page = max(1, self.page - 1)
        self.refresh_components()
        await interaction.response.edit_message(embed=self.current_embed(), view=self)

    async def _on_next(self, interaction: discord.Interaction) -> None:
        self.page = min(self.total_pages, self.page + 1)
        self.refresh_components()
        await interaction.response.edit_message(embed=self.current_embed(), view=self)

    async def _on_cancel(self, interaction: discord.Interaction) -> None:
        self.stop()
        await interaction.response.edit_message(
            embed=discord.Embed(title="Talent Builder Canceled", description="Start `/talentbuilder` again to make a new build."),
            view=None,
        )

    async def start_builder(self, interaction: discord.Interaction, hero_slug: str) -> None:
        build_data = self.repository.get_talent_build(hero_slug)
        if build_data is None:
            await interaction.response.send_message("Local talent data is missing for that hero.", ephemeral=True)
            return
        builder = TalentBuilderView(build_data=build_data, requesting_user_id=self.requesting_user_id, timeout=self.timeout)
        self.stop()
        await interaction.response.edit_message(embed=builder.current_embed(), view=builder)
        if self.message is not None:
            builder.set_message(self.message)


async def create_talent_builder_entry(
    *,
    interaction: discord.Interaction,
    repository: HeroesProfileRepository,
    requesting_user_id: int,
    hero_name: str | None,
    talent_string: str | None = None,
) -> None:
    if talent_string:
        from bot.talent_builder import parse_talent_string

        try:
            parsed = parse_talent_string(talent_string)
        except ValueError:
            await interaction.response.send_message(
                "Talent string must use HOTS format like `[T3211221,Leoric]`.",
                ephemeral=True,
            )
            return

        try:
            build_data = repository.get_talent_build_by_export_token(parsed.hero_token)
        except AmbiguousTalentBuildHeroError:
            await interaction.response.send_message(
                f"Hero token `{parsed.hero_token}` matches multiple local heroes. Resolve the local cache before using this build string.",
                ephemeral=True,
            )
            return

        if build_data is None:
            await interaction.response.send_message(
                f"Hero token `{parsed.hero_token}` was not found in local cache. Run `python heroesprofile/update_data.py --only heroes,talents` first.",
                ephemeral=True,
            )
            return

        if hero_name:
            requested_build = repository.get_talent_build(hero_name)
            if requested_build is None:
                await interaction.response.send_message(
                    "Hero talent data is not available in local cache. Run `python heroesprofile/update_data.py --only heroes,talents` first.",
                    ephemeral=True,
                )
                return
            if requested_build.hero.slug != build_data.hero.slug:
                await interaction.response.send_message(
                    f"The provided hero does not match the talent string hero `{build_data.hero.name}`.",
                    ephemeral=True,
                )
                return

        tier_options = _tier_option_map(build_data)
        for level in TALENT_LEVELS:
            picked = int(parsed.selections.get(level, 0) or 0)
            options = tier_options.get(level) or []
            if picked <= 0:
                continue
            if not any(option.index == picked for option in options):
                await interaction.response.send_message(
                    f"Talent string selects option `{picked}` for Level {level}, but `{build_data.hero.name}` only has {len(options)} cached option(s) for that tier.",
                    ephemeral=True,
                )
                return

        embeds, page_targets = format_parsed_talent_build_embeds(
            hero_name=build_data.hero.name,
            selections=parsed.selections,
            tier_options=tier_options,
        )
        if len(embeds) == 1:
            await interaction.response.send_message(
                content=f"```text\n{talent_string.strip()}\n```",
                embed=embeds[0],
                ephemeral=True,
            )
            return
        view = HeroPaginationView(embeds=embeds, page_targets=page_targets, requesting_user_id=requesting_user_id)
        await interaction.response.send_message(
            content=f"```text\n{talent_string.strip()}\n```",
            embed=view.current_embed(),
            view=view,
            ephemeral=True,
        )
        return

    if hero_name:
        build_data = repository.get_talent_build(hero_name)
        if build_data is None:
            await interaction.response.send_message(
                "Hero talent data is not available in local cache. Run `python heroesprofile/update_data.py --only heroes,talents` first.",
                ephemeral=True,
            )
            return
        view = TalentBuilderView(build_data=build_data, requesting_user_id=requesting_user_id)
        await interaction.response.send_message(embed=view.current_embed(), view=view, ephemeral=True)
        view.set_message(await interaction.original_response())
        return

    hero_view = TalentBuilderHeroSelectView(repository=repository, requesting_user_id=requesting_user_id)
    await interaction.response.send_message(embed=hero_view.current_embed(), view=hero_view, ephemeral=True)
    hero_view.set_message(await interaction.original_response())
