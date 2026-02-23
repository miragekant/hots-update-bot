from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass(frozen=True)
class BotConfig:
    bot_token: str
    guild_id: int
    news_channel_id: int
    daily_update_utc_hour: int = 15
    daily_update_utc_minute: int = 0


def _parse_int_env(name: str, raw_value: str | None, *, minimum: int = 0, maximum: int | None = None) -> int:
    if raw_value is None or raw_value.strip() == "":
        raise ValueError(f"missing required env var: {name}")
    try:
        value = int(raw_value)
    except ValueError as exc:
        raise ValueError(f"invalid integer for {name}: {raw_value}") from exc
    if value < minimum:
        raise ValueError(f"{name} must be >= {minimum}")
    if maximum is not None and value > maximum:
        raise ValueError(f"{name} must be <= {maximum}")
    return value


def load_config() -> BotConfig:
    load_dotenv()

    token = os.getenv("BOT_TOKEN")
    if token is None or token.strip() == "":
        raise ValueError("missing required env var: BOT_TOKEN")

    guild_id = _parse_int_env("GUILD_ID", os.getenv("GUILD_ID"), minimum=1)
    news_channel_id = _parse_int_env("NEWS_CHANNEL_ID", os.getenv("NEWS_CHANNEL_ID"), minimum=1)
    daily_hour = _parse_int_env("DAILY_UPDATE_UTC_HOUR", os.getenv("DAILY_UPDATE_UTC_HOUR", "15"), minimum=0, maximum=23)
    daily_minute = _parse_int_env(
        "DAILY_UPDATE_UTC_MINUTE",
        os.getenv("DAILY_UPDATE_UTC_MINUTE", "0"),
        minimum=0,
        maximum=59,
    )

    return BotConfig(
        bot_token=token,
        guild_id=guild_id,
        news_channel_id=news_channel_id,
        daily_update_utc_hour=daily_hour,
        daily_update_utc_minute=daily_minute,
    )
