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


CONFIG_SOURCE_ENV = "env"
CONFIG_SOURCE_GCP = "gcp"
_OPTIONAL_CONFIG_DEFAULTS = {
    "DAILY_UPDATE_UTC_HOUR": "15",
    "DAILY_UPDATE_UTC_MINUTE": "0",
}


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


def _load_from_env() -> dict[str, str | None]:
    return {
        "BOT_TOKEN": os.getenv("BOT_TOKEN"),
        "GUILD_ID": os.getenv("GUILD_ID"),
        "NEWS_CHANNEL_ID": os.getenv("NEWS_CHANNEL_ID"),
        "DAILY_UPDATE_UTC_HOUR": os.getenv("DAILY_UPDATE_UTC_HOUR", _OPTIONAL_CONFIG_DEFAULTS["DAILY_UPDATE_UTC_HOUR"]),
        "DAILY_UPDATE_UTC_MINUTE": os.getenv(
            "DAILY_UPDATE_UTC_MINUTE",
            _OPTIONAL_CONFIG_DEFAULTS["DAILY_UPDATE_UTC_MINUTE"],
        ),
    }


def _build_secret_manager_client():
    try:
        from google.cloud import secretmanager
    except ImportError as exc:
        raise RuntimeError("google-cloud-secret-manager is required when BOT_CONFIG_SOURCE=gcp") from exc
    return secretmanager.SecretManagerServiceClient()


def _access_secret_text(client, project_id: str, secret_name: str) -> str | None:
    secret_path = f"projects/{project_id}/secrets/{secret_name}/versions/latest"
    try:
        response = client.access_secret_version(request={"name": secret_path})
    except Exception as exc:
        if exc.__class__.__name__ == "NotFound":
            return None
        raise RuntimeError(f"failed to read secret {secret_name} from GCP Secret Manager") from exc
    return response.payload.data.decode("utf-8").strip()


def _load_from_gcp() -> dict[str, str | None]:
    project_id = os.getenv("GCP_PROJECT_ID")
    if project_id is None or project_id.strip() == "":
        raise ValueError("missing required env var: GCP_PROJECT_ID")

    client = _build_secret_manager_client()
    values = {
        "BOT_TOKEN": _access_secret_text(client, project_id, "BOT_TOKEN"),
        "GUILD_ID": _access_secret_text(client, project_id, "GUILD_ID"),
        "NEWS_CHANNEL_ID": _access_secret_text(client, project_id, "NEWS_CHANNEL_ID"),
        "DAILY_UPDATE_UTC_HOUR": _access_secret_text(client, project_id, "DAILY_UPDATE_UTC_HOUR"),
        "DAILY_UPDATE_UTC_MINUTE": _access_secret_text(client, project_id, "DAILY_UPDATE_UTC_MINUTE"),
    }
    for key, default in _OPTIONAL_CONFIG_DEFAULTS.items():
        if values[key] is None:
            values[key] = default
    return values


def _validate_config(values: dict[str, str | None]) -> BotConfig:
    token = values["BOT_TOKEN"]
    if token is None or token.strip() == "":
        raise ValueError("missing required env var: BOT_TOKEN")

    guild_id = _parse_int_env("GUILD_ID", values["GUILD_ID"], minimum=1)
    news_channel_id = _parse_int_env("NEWS_CHANNEL_ID", values["NEWS_CHANNEL_ID"], minimum=1)
    daily_hour = _parse_int_env("DAILY_UPDATE_UTC_HOUR", values["DAILY_UPDATE_UTC_HOUR"], minimum=0, maximum=23)
    daily_minute = _parse_int_env("DAILY_UPDATE_UTC_MINUTE", values["DAILY_UPDATE_UTC_MINUTE"], minimum=0, maximum=59)

    return BotConfig(
        bot_token=token,
        guild_id=guild_id,
        news_channel_id=news_channel_id,
        daily_update_utc_hour=daily_hour,
        daily_update_utc_minute=daily_minute,
    )


def load_config() -> BotConfig:
    load_dotenv()
    source = os.getenv("BOT_CONFIG_SOURCE", CONFIG_SOURCE_ENV).strip().lower()
    if source == CONFIG_SOURCE_ENV:
        return _validate_config(_load_from_env())
    if source == CONFIG_SOURCE_GCP:
        return _validate_config(_load_from_gcp())
    raise ValueError(f"invalid BOT_CONFIG_SOURCE: {source}")
