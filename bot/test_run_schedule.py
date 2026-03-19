from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone

from bot.config import BotConfig
from bot.run import HotsClient


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
