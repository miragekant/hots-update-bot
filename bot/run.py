from __future__ import annotations

import asyncio
import logging
import sys
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

import discord
from discord import app_commands
from discord.ext import tasks

# Support direct script execution: `python bot/run.py`.
if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bot.config import BotConfig, load_config
from bot.heroesprofile_repository import HeroesProfileRepository
from bot.message import (
    format_article_body_embed_pages,
    format_hero_list_embed,
    format_hero_pages,
    format_map_embed,
    format_map_list_embed,
    format_patch_embeds,
    format_patch_list_embed,
)
from bot.pagination import (
    ArticlePaginationView,
    EmbedPaginationView,
    HeroPaginationView,
    HeroesProfileListPaginationView,
    NewsPaginationView,
)
from bot.repository import NewsRepository
from bot.talent_builder_view import create_talent_builder_entry
from heroesprofile.update_data import configure_logging as configure_heroesprofile_logging
from news.update_news import configure_logging as configure_updater_logging
from news.update_news import update_news

logger = logging.getLogger("hots_bot")


def configure_bot_logging() -> None:
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(handler)
    logger.propagate = False


class HotsClient(discord.Client):
    def __init__(self, config: BotConfig):
        intents = discord.Intents.default()
        super().__init__(intents=intents)
        self.config = config
        self.tree = app_commands.CommandTree(self)
        self.repository = NewsRepository()
        self.heroesprofile_repository = HeroesProfileRepository()
        self.update_lock = asyncio.Lock()

    async def setup_hook(self) -> None:
        guild = discord.Object(id=self.config.guild_id)
        self.tree.copy_global_to(guild=guild)
        await self.tree.sync(guild=guild)
        self.daily_update_task.start()
        logger.info("commands synced for guild_id=%s", self.config.guild_id)

    async def _send_article(self, interaction: discord.Interaction, article: dict) -> None:
        pages = format_article_body_embed_pages(article)
        view = ArticlePaginationView(article=article, requesting_user_id=interaction.user.id, page_chunks=pages)
        await interaction.response.send_message(embed=view.current_embed(), view=view)

    async def send_article_to_channel(self, channel: discord.abc.Messageable, article: dict) -> None:
        pages = format_article_body_embed_pages(article)
        view = ArticlePaginationView(article=article, requesting_user_id=None, page_chunks=pages)
        await channel.send(embed=view.current_embed(), view=view)

    @tasks.loop(hours=24)
    async def daily_update_task(self) -> None:
        if self.update_lock.locked():
            logger.info("daily update skipped because another update is running")
            return

        async with self.update_lock:
            stats = await asyncio.to_thread(update_news)
            logger.info("daily update stats=%s", asdict(stats))
            if stats.new <= 0 and stats.updated <= 0:
                return

            channel = self.get_channel(self.config.news_channel_id)
            if channel is None:
                logger.error("failed to find NEWS_CHANNEL_ID=%s", self.config.news_channel_id)
                return

            await channel.send(
                f"Daily HOTS sync complete. New: {stats.new}, Updated: {stats.updated}, Unchanged: {stats.unchanged}, Failed: {stats.failed}"
            )
            latest = self.repository.get_latest_article()
            if latest is None:
                return
            full_article = self.repository.get_article_by_news_id(str(latest.get("news_id")))
            if full_article is None:
                return
            await self.send_article_to_channel(channel, full_article)

    @daily_update_task.before_loop
    async def before_daily_update_task(self) -> None:
        await self.wait_until_ready()
        now = datetime.now(timezone.utc)
        next_run = now.replace(
            hour=self.config.daily_update_utc_hour,
            minute=self.config.daily_update_utc_minute,
            second=0,
            microsecond=0,
        )
        if next_run <= now:
            next_run += timedelta(days=1)
        delay_seconds = (next_run - now).total_seconds()
        logger.info("daily update loop ready; first run at %s", next_run.isoformat())
        await asyncio.sleep(delay_seconds)


def build_client(config: BotConfig) -> HotsClient:
    client = HotsClient(config)

    def _open_hero_detail(hero_slug: str) -> tuple[discord.Embed, discord.ui.View | None] | None:
        hero_record = client.heroesprofile_repository.get_hero_by_slug(hero_slug)
        if hero_record is None:
            return None
        embeds, page_targets = format_hero_pages(
            hero_record,
            client.heroesprofile_repository.get_hero_talents(str(hero_record.get("slug") or "")),
        )
        view = HeroPaginationView(embeds=embeds, page_targets=page_targets, requesting_user_id=None)
        return view.current_embed(), view

    def _open_map_detail(map_name: str) -> tuple[discord.Embed, discord.ui.View | None] | None:
        map_record = client.heroesprofile_repository.get_map(map_name)
        if map_record is None:
            return None
        return format_map_embed(map_record), None

    def _open_patch_detail(version: str) -> tuple[discord.Embed, discord.ui.View | None] | None:
        patch_record = client.heroesprofile_repository.get_patch(version)
        if patch_record is None:
            return None
        embeds = format_patch_embeds(patch_record)
        view = EmbedPaginationView(embeds=embeds, requesting_user_id=None)
        return view.current_embed(), view

    async def talentbuilder_hero_autocomplete(
        interaction: discord.Interaction,
        current: str,
    ) -> list[app_commands.Choice[str]]:
        marker = current.strip().lower()
        results: list[app_commands.Choice[str]] = []
        for hero in client.heroesprofile_repository.list_talent_build_heroes():
            search_terms = (hero.name.lower(), hero.slug.lower(), hero.export_token.lower())
            if marker and not any(marker in term for term in search_terms):
                continue
            results.append(app_commands.Choice(name=hero.name[:100], value=hero.name))
            if len(results) >= 25:
                break
        return results

    @client.tree.command(name="hello", description="Say hi to the bot!")
    async def hello(interaction: discord.Interaction) -> None:
        await interaction.response.send_message(f"Hey {interaction.user.mention}! I'm alive.")

    @client.tree.command(name="latest", description="Show latest local HOTS article")
    async def latest(interaction: discord.Interaction) -> None:
        article_meta = client.repository.get_latest_article()
        if article_meta is None:
            await interaction.response.send_message(
                "No local news yet. Run `python news/update_news.py` or wait for the daily sync."
            )
            return

        full_article = client.repository.get_article_by_news_id(str(article_meta.get("news_id")))
        if full_article is None:
            await interaction.response.send_message("Latest article metadata exists, but local article content is missing.")
            return
        await client._send_article(interaction, full_article)

    @client.tree.command(name="news", description="Browse recent HOTS news (local cache)")
    @app_commands.describe(year="Optional year filter, e.g. 2025")
    async def news(interaction: discord.Interaction, year: int | None = None) -> None:
        if year is not None and (year < 2000 or year > 2100):
            await interaction.response.send_message("Year must be between 2000 and 2100.", ephemeral=True)
            return

        items, _total = client.repository.list_articles(year=year, offset=0, limit=10_000)
        if not items:
            await interaction.response.send_message("No local articles found for that query.", ephemeral=True)
            return

        view = NewsPaginationView(
            requesting_user_id=interaction.user.id,
            items=items,
            repository=client.repository,
            year_filter=year,
            page_size=5,
        )
        await interaction.response.send_message(embed=view.current_embed(), view=view)

    @client.tree.command(name="hero", description="Show a hero from cached HeroesProfile data")
    @app_commands.describe(name="Hero name, alias, or translation")
    async def hero(interaction: discord.Interaction, name: str | None = None) -> None:
        repo = client.heroesprofile_repository
        if name is None:
            heroes = repo.list_heroes()
            if not heroes:
                await interaction.response.send_message(
                    "Hero data is not available in local cache. Run `python heroesprofile/update_data.py` first.",
                    ephemeral=True,
                )
                return

            view = HeroesProfileListPaginationView(
                requesting_user_id=interaction.user.id,
                items=heroes,
                page_size=10,
                select_placeholder="Select a hero to open",
                embed_builder=format_hero_list_embed,
                option_label_getter=lambda item: str(item.get("name") or "Unknown Hero"),
                option_description_getter=lambda item: str(item.get("new_role") or item.get("role") or "Unknown role"),
                option_value_getter=lambda item: str(item.get("slug") or ""),
                detail_loader=_open_hero_detail,
            )
            await interaction.response.send_message(embed=view.current_embed(), view=view)
            return

        hero_record = repo.get_hero(name)
        if hero_record is None:
            await interaction.response.send_message(
                "Hero data is not available in local cache. Run `python heroesprofile/update_data.py` first.",
                ephemeral=True,
            )
            return

        embeds, page_targets = format_hero_pages(hero_record, repo.get_hero_talents(str(hero_record.get("slug") or "")))
        view = HeroPaginationView(embeds=embeds, page_targets=page_targets, requesting_user_id=interaction.user.id)
        await interaction.response.send_message(embed=view.current_embed(), view=view)

    @client.tree.command(name="map", description="Show a HOTS map from cached HeroesProfile data")
    @app_commands.describe(name="Map name or short name")
    async def map_command(interaction: discord.Interaction, name: str | None = None) -> None:
        if name is None:
            maps = client.heroesprofile_repository.list_maps()
            if not maps:
                await interaction.response.send_message(
                    "Map data is not available in local cache. Run `python heroesprofile/update_data.py` first.",
                    ephemeral=True,
                )
                return

            view = HeroesProfileListPaginationView(
                requesting_user_id=interaction.user.id,
                items=maps,
                page_size=10,
                select_placeholder="Select a map to open",
                embed_builder=format_map_list_embed,
                option_label_getter=lambda item: str(item.get("name") or "Unknown Map"),
                option_description_getter=lambda item: str(item.get("type") or "Unknown type"),
                option_value_getter=lambda item: str(item.get("name") or ""),
                detail_loader=_open_map_detail,
            )
            await interaction.response.send_message(embed=view.current_embed(), view=view)
            return

        map_record = client.heroesprofile_repository.get_map(name)
        if map_record is None:
            await interaction.response.send_message(
                "Map data is not available in local cache. Run `python heroesprofile/update_data.py` first.",
                ephemeral=True,
            )
            return

        await interaction.response.send_message(embed=format_map_embed(map_record))

    @client.tree.command(name="patch", description="Show a HOTS patch family from cached HeroesProfile data")
    @app_commands.describe(version="Patch family like 2.55 or full build like 2.55.15.96477")
    async def patch(interaction: discord.Interaction, version: str | None = None) -> None:
        if version is None:
            patches = client.heroesprofile_repository.list_patches()
            if not patches:
                await interaction.response.send_message(
                    "Patch data is not available in local cache. Run `python heroesprofile/update_data.py` first.",
                    ephemeral=True,
                )
                return

            view = HeroesProfileListPaginationView(
                requesting_user_id=interaction.user.id,
                items=patches,
                page_size=10,
                select_placeholder="Select a patch to open",
                embed_builder=format_patch_list_embed,
                option_label_getter=lambda item: str(item.get("version_family") or "Unknown Patch"),
                option_description_getter=lambda item: f"{int(item.get('build_count') or len(item.get('builds') or []))} builds",
                option_value_getter=lambda item: str(item.get("version_family") or ""),
                detail_loader=_open_patch_detail,
            )
            await interaction.response.send_message(embed=view.current_embed(), view=view)
            return

        patch_record = client.heroesprofile_repository.get_patch(version)
        if patch_record is None:
            await interaction.response.send_message(
                "Patch data is not available in local cache. Run `python heroesprofile/update_data.py` first.",
                ephemeral=True,
            )
            return

        embeds = format_patch_embeds(patch_record)
        view = EmbedPaginationView(embeds=embeds, requesting_user_id=interaction.user.id)
        await interaction.response.send_message(embed=view.current_embed(), view=view)

    @client.tree.command(name="talentbuilder", description="Create or parse a HOTS talent build from local cache")
    @app_commands.describe(
        hero="Optional hero to start with immediately, or validate against the parsed string",
        talent_string="Optional HOTS build string like [T3211221,Leoric]",
    )
    @app_commands.autocomplete(hero=talentbuilder_hero_autocomplete)
    async def talentbuilder(interaction: discord.Interaction, hero: str | None = None, talent_string: str | None = None) -> None:
        repo = client.heroesprofile_repository
        if not repo.has_data():
            await interaction.response.send_message(
                "Hero data is not available in local cache. Run `python heroesprofile/update_data.py` first.",
                ephemeral=True,
            )
            return

        heroes = repo.list_talent_builder_heroes()
        if not heroes:
            await interaction.response.send_message(
                "No local hero talent data is available. Run `python heroesprofile/update_data.py --only heroes,talents` first.",
                ephemeral=True,
            )
            return
        await create_talent_builder_entry(
            interaction=interaction,
            repository=repo,
            requesting_user_id=interaction.user.id,
            hero_name=hero,
            talent_string=talent_string,
        )

    return client


def main() -> None:
    configure_bot_logging()
    configure_updater_logging(verbose=False)
    configure_heroesprofile_logging(verbose=False)
    config = load_config()
    client = build_client(config)
    client.run(config.bot_token, log_level=logging.INFO, root_logger=False)


if __name__ == "__main__":
    main()
