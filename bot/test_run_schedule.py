from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone

from bot.config import BotConfig
from bot.run import HotsClient
from news.update_news import UpdateStats


def _build_client(cron: str = "0 15 * * *") -> HotsClient:
    return HotsClient(
        BotConfig(
            bot_token="token",
            guild_id=123,
            news_channel_id=456,
            daily_update_cron=cron,
        )
    )


def test_should_run_daily_update_matches_once_per_minute():
    client = _build_client("*/30 * * * *")
    run_at = datetime(2026, 3, 18, 10, 30, 45, tzinfo=timezone.utc)

    assert client.should_run_daily_update(run_at) is True
    assert client.should_run_daily_update(run_at.replace(second=59)) is False
    assert client.should_run_daily_update(datetime(2026, 3, 18, 10, 31, tzinfo=timezone.utc)) is False
    assert client.should_run_daily_update(datetime(2026, 3, 18, 11, 0, tzinfo=timezone.utc)) is True


def test_should_run_daily_update_rejects_non_matching_minute():
    client = _build_client("15 10 * * 1-5")

    assert client.should_run_daily_update(datetime(2026, 3, 18, 10, 14, tzinfo=timezone.utc)) is False
    assert client.should_run_daily_update(datetime(2026, 3, 22, 10, 15, tzinfo=timezone.utc)) is False


def test_next_daily_update_after_handles_weekday_boundary():
    client = _build_client("15 10 * * 1-5")

    next_run = client.next_daily_update_after(datetime(2026, 3, 20, 10, 15, tzinfo=timezone.utc))

    assert next_run == datetime(2026, 3, 23, 10, 15, tzinfo=timezone.utc)


def test_next_daily_update_after_handles_multiple_runs_per_day():
    client = _build_client("*/30 9-10 * * *")

    next_run = client.next_daily_update_after(datetime(2026, 3, 18, 9, 30, tzinfo=timezone.utc))

    assert next_run == datetime(2026, 3, 18, 10, 0, tzinfo=timezone.utc)


def test_before_daily_update_task_sleeps_until_next_run(monkeypatch):
    client = _build_client("15 10 * * 1-5")
    now = datetime(2026, 3, 20, 10, 0, 30, tzinfo=timezone.utc)
    slept: list[float] = []

    class _FakeDateTime:
        @staticmethod
        def now(tz=None):
            if tz is None:
                return now
            return now.astimezone(tz)

    async def _fake_wait_until_ready():
        return None

    async def _fake_sleep(delay_seconds: float):
        slept.append(delay_seconds)

    monkeypatch.setattr("bot.run.datetime", _FakeDateTime)
    monkeypatch.setattr(client, "wait_until_ready", _fake_wait_until_ready)
    monkeypatch.setattr("bot.run.asyncio.sleep", _fake_sleep)

    asyncio.run(client.before_daily_update_task())

    assert slept == [870.0]


class _FakeChannel:
    def __init__(self) -> None:
        self.messages: list[dict[str, object]] = []

    async def send(self, content: str | None = None, *, embed=None, view=None) -> None:
        self.messages.append({"content": content, "embed": embed, "view": view})


def test_daily_update_task_posts_summary_and_each_new_article(monkeypatch):
    async def _run() -> None:
        client = _build_client()
        channel = _FakeChannel()
        posted_articles: list[str] = []
        stats = UpdateStats(new=2, updated=1, unchanged=3, failed=0, new_news_ids=["1001", "1002"])

        async def _fake_send_article_to_channel(_channel, article: dict) -> None:
            posted_articles.append(str(article["news_id"]))

        monkeypatch.setattr(client, "should_run_daily_update", lambda now: True)
        monkeypatch.setattr(client, "get_channel", lambda channel_id: channel if channel_id == 456 else None)
        monkeypatch.setattr(
            client.repository,
            "get_article_by_news_id",
            lambda news_id: {
                "news_id": news_id,
                "title": news_id,
                "timestamp": {"1001": "2025-10-02T00:00:00Z", "1002": "2025-10-01T00:00:00Z"}[news_id],
            },
        )
        monkeypatch.setattr(client, "send_article_to_channel", _fake_send_article_to_channel)
        monkeypatch.setattr("bot.run.update_news", lambda: stats)
        monkeypatch.setattr("bot.run.asyncio.to_thread", lambda func: asyncio.sleep(0, result=func()))

        await client.daily_update_task.coro(client)

        assert channel.messages == [
            {
                "content": "Daily HOTS sync complete. New: 2, Updated: 1, Unchanged: 3, Failed: 0",
                "embed": None,
                "view": None,
            }
        ]
        assert posted_articles == ["1002", "1001"]

    asyncio.run(_run())


def test_daily_update_task_update_only_run_skips_article_posts(monkeypatch):
    async def _run() -> None:
        client = _build_client()
        channel = _FakeChannel()
        send_calls: list[str] = []
        stats = UpdateStats(new=0, updated=2, unchanged=4, failed=0, new_news_ids=[])

        async def _fake_send_article_to_channel(_channel, article: dict) -> None:
            send_calls.append(str(article["news_id"]))

        monkeypatch.setattr(client, "should_run_daily_update", lambda now: True)
        monkeypatch.setattr(client, "get_channel", lambda channel_id: channel if channel_id == 456 else None)
        monkeypatch.setattr(client, "send_article_to_channel", _fake_send_article_to_channel)
        monkeypatch.setattr("bot.run.update_news", lambda: stats)
        monkeypatch.setattr("bot.run.asyncio.to_thread", lambda func: asyncio.sleep(0, result=func()))

        await client.daily_update_task.coro(client)

        assert channel.messages == [
            {
                "content": "Daily HOTS sync complete. New: 0, Updated: 2, Unchanged: 4, Failed: 0",
                "embed": None,
                "view": None,
            }
        ]
        assert send_calls == []

    asyncio.run(_run())


def test_daily_update_task_missing_channel_returns_cleanly(monkeypatch):
    async def _run() -> None:
        client = _build_client()
        stats = UpdateStats(new=1, updated=0, unchanged=0, failed=0, new_news_ids=["1001"])

        monkeypatch.setattr(client, "should_run_daily_update", lambda now: True)
        monkeypatch.setattr(client, "get_channel", lambda channel_id: None)
        monkeypatch.setattr("bot.run.update_news", lambda: stats)
        monkeypatch.setattr("bot.run.asyncio.to_thread", lambda func: asyncio.sleep(0, result=func()))

        await client.daily_update_task.coro(client)

    asyncio.run(_run())


def test_daily_update_task_skips_missing_cached_article_and_continues(monkeypatch):
    async def _run() -> None:
        client = _build_client()
        channel = _FakeChannel()
        posted_articles: list[str] = []
        stats = UpdateStats(new=3, updated=0, unchanged=0, failed=0, new_news_ids=["1001", "1002", "1003"])

        async def _fake_send_article_to_channel(_channel, article: dict) -> None:
            posted_articles.append(str(article["news_id"]))

        def _get_article(news_id: str):
            if news_id == "1002":
                return None
            return {
                "news_id": news_id,
                "title": news_id,
                "timestamp": {"1001": "2025-10-02T00:00:00Z", "1003": "2025-10-01T00:00:00Z"}[news_id],
            }

        monkeypatch.setattr(client, "should_run_daily_update", lambda now: True)
        monkeypatch.setattr(client, "get_channel", lambda channel_id: channel if channel_id == 456 else None)
        monkeypatch.setattr(client.repository, "get_article_by_news_id", _get_article)
        monkeypatch.setattr(client, "send_article_to_channel", _fake_send_article_to_channel)
        monkeypatch.setattr("bot.run.update_news", lambda: stats)
        monkeypatch.setattr("bot.run.asyncio.to_thread", lambda func: asyncio.sleep(0, result=func()))

        await client.daily_update_task.coro(client)

        assert channel.messages == [
            {
                "content": "Daily HOTS sync complete. New: 3, Updated: 0, Unchanged: 0, Failed: 0",
                "embed": None,
                "view": None,
            }
        ]
        assert posted_articles == ["1003", "1001"]

    asyncio.run(_run())
