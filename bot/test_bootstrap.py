from __future__ import annotations

import pytest

from bot.bootstrap import decide_bootstrap_sync, parse_bool_env


def test_parse_bool_env_uses_default_for_missing_value():
    assert parse_bool_env("FLAG", None, default=True) is True
    assert parse_bool_env("FLAG", "", default=False) is False


def test_parse_bool_env_accepts_common_true_and_false_values():
    assert parse_bool_env("FLAG", "true", default=False) is True
    assert parse_bool_env("FLAG", "1", default=False) is True
    assert parse_bool_env("FLAG", "off", default=True) is False
    assert parse_bool_env("FLAG", "no", default=True) is False


def test_parse_bool_env_rejects_invalid_values():
    with pytest.raises(ValueError, match="FLAG must be a boolean value"):
        parse_bool_env("FLAG", "maybe", default=False)


def test_decide_bootstrap_sync_runs_when_any_required_cache_is_missing(tmp_path):
    decision = decide_bootstrap_sync({}, news_index_path=tmp_path / "news.json", heroes_manifest_path=tmp_path / "manifest.json")

    assert decision.should_sync is True
    assert decision.reason == "bootstrap required because local cache is incomplete"


def test_decide_bootstrap_sync_skips_when_both_caches_exist(tmp_path):
    news_index = tmp_path / "news" / "index.json"
    news_index.parent.mkdir()
    news_index.write_text("{}", encoding="utf-8")
    manifest = tmp_path / "heroesprofile" / "manifest.json"
    manifest.parent.mkdir()
    manifest.write_text("{}", encoding="utf-8")

    decision = decide_bootstrap_sync({}, news_index_path=news_index, heroes_manifest_path=manifest)

    assert decision.should_sync is False
    assert decision.reason == "bootstrap skipped because local cache is already present"


def test_decide_bootstrap_sync_honors_skip_even_when_cache_is_missing(tmp_path):
    decision = decide_bootstrap_sync(
        {"BOOTSTRAP_SYNC_SKIP": "true"},
        news_index_path=tmp_path / "news" / "index.json",
        heroes_manifest_path=tmp_path / "heroesprofile" / "manifest.json",
    )

    assert decision.should_sync is False
    assert decision.reason == "bootstrap disabled by BOOTSTRAP_SYNC_SKIP"


def test_decide_bootstrap_sync_honors_force_even_when_cache_exists(tmp_path):
    news_index = tmp_path / "news" / "index.json"
    news_index.parent.mkdir()
    news_index.write_text("{}", encoding="utf-8")
    manifest = tmp_path / "heroesprofile" / "manifest.json"
    manifest.parent.mkdir()
    manifest.write_text("{}", encoding="utf-8")

    decision = decide_bootstrap_sync(
        {"BOOTSTRAP_SYNC_FORCE": "true"},
        news_index_path=news_index,
        heroes_manifest_path=manifest,
    )

    assert decision.should_sync is True
    assert decision.reason == "bootstrap forced by BOOTSTRAP_SYNC_FORCE"


def test_decide_bootstrap_sync_skips_when_on_empty_is_disabled(tmp_path):
    decision = decide_bootstrap_sync(
        {"BOOTSTRAP_SYNC_ON_EMPTY": "false"},
        news_index_path=tmp_path / "news" / "index.json",
        heroes_manifest_path=tmp_path / "heroesprofile" / "manifest.json",
    )

    assert decision.should_sync is False
    assert decision.reason == "bootstrap disabled because BOOTSTRAP_SYNC_ON_EMPTY is false"
