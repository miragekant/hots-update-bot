from __future__ import annotations

from types import SimpleNamespace

import pytest

from bot import config


class _FakeSecretClient:
    def __init__(self, secrets: dict[str, str]):
        self._secrets = secrets

    def access_secret_version(self, request: dict[str, str]):
        secret_name = request["name"].split("/")[3]
        if secret_name not in self._secrets:
            raise type("NotFound", (Exception,), {})()
        value = self._secrets[secret_name].encode("utf-8")
        return SimpleNamespace(payload=SimpleNamespace(data=value))


@pytest.fixture(autouse=True)
def _clear_env(monkeypatch):
    monkeypatch.setattr(config, "load_dotenv", lambda: None)
    for name in (
        "BOT_CONFIG_SOURCE",
        "BOT_TOKEN",
        "GUILD_ID",
        "NEWS_CHANNEL_ID",
        "DAILY_UPDATE_UTC_HOUR",
        "DAILY_UPDATE_UTC_MINUTE",
        "GCP_PROJECT_ID",
    ):
        monkeypatch.delenv(name, raising=False)


def test_load_config_from_env(monkeypatch):
    monkeypatch.setenv("BOT_TOKEN", "token")
    monkeypatch.setenv("GUILD_ID", "123")
    monkeypatch.setenv("NEWS_CHANNEL_ID", "456")

    loaded = config.load_config()

    assert loaded == config.BotConfig(
        bot_token="token",
        guild_id=123,
        news_channel_id=456,
        daily_update_utc_hour=15,
        daily_update_utc_minute=0,
    )


def test_load_config_from_gcp(monkeypatch):
    monkeypatch.setenv("BOT_CONFIG_SOURCE", "gcp")
    monkeypatch.setenv("GCP_PROJECT_ID", "project-1")
    monkeypatch.setattr(
        config,
        "_build_secret_manager_client",
        lambda: _FakeSecretClient(
            {
                "BOT_TOKEN": "token",
                "GUILD_ID": "123",
                "NEWS_CHANNEL_ID": "456",
            }
        ),
    )

    loaded = config.load_config()

    assert loaded == config.BotConfig(
        bot_token="token",
        guild_id=123,
        news_channel_id=456,
        daily_update_utc_hour=15,
        daily_update_utc_minute=0,
    )


def test_load_config_requires_gcp_project_id(monkeypatch):
    monkeypatch.setenv("BOT_CONFIG_SOURCE", "gcp")

    with pytest.raises(ValueError, match="GCP_PROJECT_ID"):
        config.load_config()


def test_load_config_rejects_unknown_source(monkeypatch):
    monkeypatch.setenv("BOT_CONFIG_SOURCE", "nope")

    with pytest.raises(ValueError, match="invalid BOT_CONFIG_SOURCE"):
        config.load_config()


def test_load_config_rejects_invalid_integer(monkeypatch):
    monkeypatch.setenv("BOT_TOKEN", "token")
    monkeypatch.setenv("GUILD_ID", "abc")
    monkeypatch.setenv("NEWS_CHANNEL_ID", "456")

    with pytest.raises(ValueError, match="invalid integer for GUILD_ID"):
        config.load_config()


def test_load_config_reports_missing_secret_manager_dependency(monkeypatch):
    monkeypatch.setenv("BOT_CONFIG_SOURCE", "gcp")
    monkeypatch.setenv("GCP_PROJECT_ID", "project-1")
    monkeypatch.setattr(
        config,
        "_build_secret_manager_client",
        lambda: (_ for _ in ()).throw(RuntimeError("google-cloud-secret-manager is required when BOT_CONFIG_SOURCE=gcp")),
    )

    with pytest.raises(RuntimeError, match="google-cloud-secret-manager"):
        config.load_config()


def test_load_config_rejects_missing_required_gcp_secret(monkeypatch):
    monkeypatch.setenv("BOT_CONFIG_SOURCE", "gcp")
    monkeypatch.setenv("GCP_PROJECT_ID", "project-1")
    monkeypatch.setattr(
        config,
        "_build_secret_manager_client",
        lambda: _FakeSecretClient(
            {
                "BOT_TOKEN": "token",
                "NEWS_CHANNEL_ID": "456",
            }
        ),
    )

    with pytest.raises(ValueError, match="GUILD_ID"):
        config.load_config()
