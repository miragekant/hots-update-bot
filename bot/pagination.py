from __future__ import annotations

import math
from typing import Any

import discord

from bot.message import format_article_body_embed_pages, format_article_embed, format_news_list_embed
from bot.repository import NewsRepository


def compute_total_pages(total_items: int, page_size: int) -> int:
    if page_size <= 0:
        raise ValueError("page_size must be > 0")
    return max(1, math.ceil(max(total_items, 0) / page_size))


def page_slice(items: list[dict[str, Any]], page: int, page_size: int) -> list[dict[str, Any]]:
    if page_size <= 0:
        raise ValueError("page_size must be > 0")
    if page <= 0:
        page = 1
    start = (page - 1) * page_size
    return items[start : start + page_size]


def build_article_page_embed(article: dict[str, Any], page_chunk: str, page: int, total_pages: int) -> discord.Embed:
    embed = format_article_embed(article)
    summary = embed.description
    embed.description = page_chunk or "_No article body available._"
    if summary and summary != embed.description:
        summary_value = summary if len(summary) <= 1024 else f"{summary[:1021]}..."
        embed.add_field(name="Summary", value=summary_value, inline=False)
    embed.set_footer(text=f"Page {page}/{total_pages}")
    return embed


class ArticlePaginationView(discord.ui.View):
    def __init__(
        self,
        *,
        article: dict[str, Any],
        requesting_user_id: int | None,
        page_chunks: list[str] | None = None,
        timeout: float = 300,
    ) -> None:
        super().__init__(timeout=timeout)
        self.article = article
        self.requesting_user_id = requesting_user_id
        self.page_chunks = page_chunks or format_article_body_embed_pages(article)
        self.page = 1
        self.total_pages = compute_total_pages(len(self.page_chunks), 1)

        self.prev_button = discord.ui.Button(label="Prev", style=discord.ButtonStyle.secondary)
        self.next_button = discord.ui.Button(label="Next", style=discord.ButtonStyle.secondary)
        self.prev_button.callback = self._on_prev
        self.next_button.callback = self._on_next

        self.add_item(self.prev_button)
        self.add_item(self.next_button)

        original_url = article.get("url")
        if isinstance(original_url, str) and original_url.strip():
            self.add_item(discord.ui.Button(label="Open Original", style=discord.ButtonStyle.link, url=original_url))

        self._refresh_components()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if self.requesting_user_id is None or interaction.user.id == self.requesting_user_id:
            return True
        await interaction.response.send_message("Only the original requester can use these controls.", ephemeral=True)
        return False

    def current_embed(self) -> discord.Embed:
        chunk = self.page_chunks[self.page - 1] if self.page_chunks else "_No article body available._"
        return build_article_page_embed(self.article, chunk, self.page, self.total_pages)

    def _refresh_components(self) -> None:
        self.prev_button.disabled = self.page <= 1
        self.next_button.disabled = self.page >= self.total_pages

    async def _on_prev(self, interaction: discord.Interaction) -> None:
        self.page = max(1, self.page - 1)
        self._refresh_components()
        await interaction.response.edit_message(embed=self.current_embed(), view=self)

    async def _on_next(self, interaction: discord.Interaction) -> None:
        self.page = min(self.total_pages, self.page + 1)
        self._refresh_components()
        await interaction.response.edit_message(embed=self.current_embed(), view=self)


class NewsPaginationView(discord.ui.View):
    def __init__(
        self,
        *,
        requesting_user_id: int,
        items: list[dict[str, Any]],
        repository: NewsRepository,
        year_filter: int | None,
        page_size: int = 5,
    ) -> None:
        super().__init__(timeout=300)
        self.requesting_user_id = requesting_user_id
        self.items = items
        self.repository = repository
        self.year_filter = year_filter
        self.page_size = page_size
        self.page = 1
        self.total_pages = compute_total_pages(len(items), page_size)

        self.prev_button = discord.ui.Button(label="Prev", style=discord.ButtonStyle.secondary)
        self.next_button = discord.ui.Button(label="Next", style=discord.ButtonStyle.secondary)
        self.select = discord.ui.Select(placeholder="Select an article to open")

        self.prev_button.callback = self._on_prev
        self.next_button.callback = self._on_next
        self.select.callback = self._on_select

        self.add_item(self.prev_button)
        self.add_item(self.next_button)
        self.add_item(self.select)
        self._refresh_components()

    def _current_items(self) -> list[dict[str, Any]]:
        return page_slice(self.items, self.page, self.page_size)

    def current_embed(self) -> discord.Embed:
        return format_news_list_embed(self._current_items(), self.page, self.total_pages, self.year_filter)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == self.requesting_user_id:
            return True
        await interaction.response.send_message("Only the original requester can use these controls.", ephemeral=True)
        return False

    def _refresh_components(self) -> None:
        self.prev_button.disabled = self.page <= 1
        self.next_button.disabled = self.page >= self.total_pages

        options: list[discord.SelectOption] = []
        for item in self._current_items():
            news_id = str(item.get("news_id") or "")
            title = str(item.get("title") or "Untitled")
            description = str(item.get("timestamp") or "Unknown date")
            options.append(discord.SelectOption(label=title[:100], description=description[:100], value=news_id))
        if not options:
            options.append(discord.SelectOption(label="No articles", value="__none__", description="No article on this page"))

        self.select.options = options
        self.select.disabled = options[0].value == "__none__"

    async def _on_prev(self, interaction: discord.Interaction) -> None:
        self.page = max(1, self.page - 1)
        self._refresh_components()
        await interaction.response.edit_message(embed=self.current_embed(), view=self)

    async def _on_next(self, interaction: discord.Interaction) -> None:
        self.page = min(self.total_pages, self.page + 1)
        self._refresh_components()
        await interaction.response.edit_message(embed=self.current_embed(), view=self)

    async def _on_select(self, interaction: discord.Interaction) -> None:
        selected = self.select.values[0]
        if selected == "__none__":
            await interaction.response.send_message("No article available on this page.", ephemeral=True)
            return

        article = self.repository.get_article_by_news_id(selected)
        if article is None:
            await interaction.response.send_message("Article is not available in local cache.", ephemeral=True)
            return

        page_chunks = format_article_body_embed_pages(article)
        article_view = ArticlePaginationView(
            article=article,
            requesting_user_id=interaction.user.id,
            page_chunks=page_chunks,
        )
        await interaction.response.send_message(embed=article_view.current_embed(), view=article_view)
