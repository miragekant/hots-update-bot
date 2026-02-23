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
from bot.message import format_article_body_embed_pages
from bot.pagination import ArticlePaginationView, NewsPaginationView
from bot.repository import NewsRepository
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

    return client


def main() -> None:
    configure_bot_logging()
    configure_updater_logging(verbose=False)
    config = load_config()
    client = build_client(config)
    client.run(config.bot_token, log_level=logging.INFO, root_logger=False)


if __name__ == "__main__":
    main()
