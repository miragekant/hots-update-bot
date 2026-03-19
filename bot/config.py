from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv


@dataclass(frozen=True)
class BotConfig:
    bot_token: str
    guild_id: int
    news_channel_id: int
    daily_update_cron: str = "0 15 * * *"


@dataclass(frozen=True)
class CronSchedule:
    expression: str
    minutes: frozenset[int]
    hours: frozenset[int]
    days_of_month: frozenset[int]
    months: frozenset[int]
    days_of_week: frozenset[int]
    day_of_month_wildcard: bool
    day_of_week_wildcard: bool

    def matches(self, dt: datetime) -> bool:
        cron_day_of_week = (dt.weekday() + 1) % 7
        day_of_month_match = dt.day in self.days_of_month
        day_of_week_match = cron_day_of_week in self.days_of_week
        if self.day_of_month_wildcard and self.day_of_week_wildcard:
            day_match = True
        elif self.day_of_month_wildcard:
            day_match = day_of_week_match
        elif self.day_of_week_wildcard:
            day_match = day_of_month_match
        else:
            day_match = day_of_month_match or day_of_week_match
        return (
            dt.minute in self.minutes
            and dt.hour in self.hours
            and dt.month in self.months
            and day_match
        )

    def next_run_after(self, after: datetime) -> datetime:
        candidate = after.astimezone(timezone.utc).replace(second=0, microsecond=0) + timedelta(minutes=1)
        for _ in range(366 * 24 * 60):
            if self.matches(candidate):
                return candidate
            candidate += timedelta(minutes=1)
        raise RuntimeError(f"failed to find next run time for cron expression: {self.expression}")


CONFIG_SOURCE_ENV = "env"
CONFIG_SOURCE_GCP = "gcp"
_OPTIONAL_CONFIG_DEFAULTS = {
    "DAILY_UPDATE_CRON": "0 15 * * *",
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


def _parse_cron_field(field: str, *, name: str, minimum: int, maximum: int) -> tuple[frozenset[int], bool]:
    if field.strip() == "":
        raise ValueError(f"{name} field is empty")

    wildcard = field == "*"
    allowed: set[int] = set()
    for part in field.split(","):
        part = part.strip()
        if part == "":
            raise ValueError(f"{name} field contains an empty list item")

        step = 1
        if "/" in part:
            base, step_raw = part.split("/", 1)
            if base == "" or step_raw == "":
                raise ValueError(f"{name} field has an invalid step expression: {part}")
            step = _parse_int_env(f"{name} step", step_raw, minimum=1)
        else:
            base = part

        if base == "*":
            start = minimum
            end = maximum
        elif "-" in base:
            start_raw, end_raw = base.split("-", 1)
            start = _parse_int_env(name, start_raw, minimum=minimum, maximum=maximum)
            end = _parse_int_env(name, end_raw, minimum=minimum, maximum=maximum)
            if end < start:
                raise ValueError(f"{name} field has an invalid range: {part}")
        else:
            value = _parse_int_env(name, base, minimum=minimum, maximum=maximum)
            allowed.add(0 if name == "day_of_week" and value == 7 else value)
            continue

        for value in range(start, end + 1, step):
            allowed.add(0 if name == "day_of_week" and value == 7 else value)

    if not allowed:
        raise ValueError(f"{name} field produced no values")
    return frozenset(allowed), wildcard


def parse_cron_schedule(raw_value: str | None, *, env_name: str = "DAILY_UPDATE_CRON") -> CronSchedule:
    if raw_value is None or raw_value.strip() == "":
        raise ValueError(f"missing required env var: {env_name}")

    parts = raw_value.split()
    if len(parts) != 5:
        raise ValueError(f"{env_name} must be a 5-field cron expression")

    try:
        minutes, _ = _parse_cron_field(parts[0], name="minute", minimum=0, maximum=59)
        hours, _ = _parse_cron_field(parts[1], name="hour", minimum=0, maximum=23)
        days_of_month, dom_wildcard = _parse_cron_field(parts[2], name="day_of_month", minimum=1, maximum=31)
        months, _ = _parse_cron_field(parts[3], name="month", minimum=1, maximum=12)
        days_of_week, dow_wildcard = _parse_cron_field(parts[4], name="day_of_week", minimum=0, maximum=7)
    except ValueError as exc:
        raise ValueError(f"invalid cron expression for {env_name}: {raw_value}") from exc

    return CronSchedule(
        expression=raw_value,
        minutes=minutes,
        hours=hours,
        days_of_month=days_of_month,
        months=months,
        days_of_week=days_of_week,
        day_of_month_wildcard=dom_wildcard,
        day_of_week_wildcard=dow_wildcard,
    )


def _load_from_env() -> dict[str, str | None]:
    return {
        "BOT_TOKEN": os.getenv("BOT_TOKEN"),
        "GUILD_ID": os.getenv("GUILD_ID"),
        "NEWS_CHANNEL_ID": os.getenv("NEWS_CHANNEL_ID"),
        "DAILY_UPDATE_CRON": os.getenv("DAILY_UPDATE_CRON", _OPTIONAL_CONFIG_DEFAULTS["DAILY_UPDATE_CRON"]),
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
        "DAILY_UPDATE_CRON": _access_secret_text(client, project_id, "DAILY_UPDATE_CRON"),
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
    daily_update_cron = parse_cron_schedule(values["DAILY_UPDATE_CRON"]).expression

    return BotConfig(
        bot_token=token,
        guild_id=guild_id,
        news_channel_id=news_channel_id,
        daily_update_cron=daily_update_cron,
    )


def load_config() -> BotConfig:
    load_dotenv()
    source = os.getenv("BOT_CONFIG_SOURCE", CONFIG_SOURCE_ENV).strip().lower()
    if source == CONFIG_SOURCE_ENV:
        return _validate_config(_load_from_env())
    if source == CONFIG_SOURCE_GCP:
        return _validate_config(_load_from_gcp())
    raise ValueError(f"invalid BOT_CONFIG_SOURCE: {source}")
