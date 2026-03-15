from __future__ import annotations

import json
from pathlib import Path

from bot.heroesprofile_repository import HeroesProfileRepository
from bot.talent_builder import build_talent_string, build_talent_string_for_hero, resolve_hero_token


def _write(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


def test_heroesprofile_repository_hero_lookup_by_alias_and_translation(tmp_path: Path):
    _write(
        tmp_path / "heroes" / "index.json",
        {
            "heroes": [
                {
                    "name": "Anub'arak",
                    "slug": "anubarak",
                    "short_name": "anubarak",
                    "alt_name": "Anubarak",
                    "aliases": ["Anub'arak", "Anubarak", "ануб'арак"],
                    "file_path": str(tmp_path / "heroes" / "by_name" / "anubarak.json"),
                }
            ]
        },
    )
    _write(tmp_path / "heroes" / "by_name" / "anubarak.json", {"name": "Anub'arak", "slug": "anubarak"})

    repo = HeroesProfileRepository(data_root=tmp_path)
    assert repo.get_hero("Anubarak")["slug"] == "anubarak"
    assert repo.get_hero("ануб'арак")["slug"] == "anubarak"


def test_heroesprofile_repository_map_and_patch_lookup(tmp_path: Path):
    _write(
        tmp_path / "maps" / "index.json",
        {
            "maps": [
                {
                    "name": "Cursed Hollow",
                    "short_name": "CursedHollow",
                    "aliases": ["Cursed Hollow", "CursedHollow"],
                    "type": "standard",
                }
            ]
        },
    )
    _write(
        tmp_path / "patches" / "index.json",
        {
            "patches": [
                {
                    "version_family": "2.55",
                    "builds": ["2.55.15.96477", "2.55.14.95918"],
                    "build_count": 2,
                }
            ]
        },
    )

    repo = HeroesProfileRepository(data_root=tmp_path)
    assert repo.get_map("CursedHollow")["name"] == "Cursed Hollow"
    assert repo.get_patch("2.55")["build_count"] == 2
    assert repo.get_patch("2.55.15.96477")["matched_build"] == "2.55.15.96477"


def test_heroesprofile_repository_lists_talent_builder_heroes_and_build_data(tmp_path: Path):
    _write(
        tmp_path / "heroes" / "index.json",
        {
            "heroes": [
                {
                    "name": "The Lost Vikings",
                    "slug": "thelostvikings",
                    "short_name": "thelostvikings",
                    "build_copy_name": "LostVikings",
                    "file_path": str(tmp_path / "heroes" / "by_name" / "thelostvikings.json"),
                },
                {
                    "name": "No Talents Hero",
                    "slug": "notalents",
                    "short_name": "notalents",
                    "file_path": str(tmp_path / "heroes" / "by_name" / "notalents.json"),
                },
            ]
        },
    )
    _write(
        tmp_path / "heroes" / "by_name" / "thelostvikings.json",
        {
            "name": "The Lost Vikings",
            "slug": "thelostvikings",
            "build_copy_name": "LostVikings",
        },
    )
    _write(tmp_path / "heroes" / "by_name" / "notalents.json", {"name": "No Talents Hero", "slug": "notalents"})
    _write(
        tmp_path / "talents" / "by_hero" / "thelostvikings.json",
        {
            "levels": ["1", "4"],
            "talents_by_level": {
                "1": [
                    {"talent_id": 1, "title": "Olaf the Stout", "description": "A", "hotkey": "Passive", "sort": "1"},
                    {"talent_id": 2, "title": "Spy Games", "description": "B", "hotkey": "Passive", "sort": "2"},
                ],
                "4": [{"talent_id": 3, "title": "Pain Don't Hurt", "description": "C", "hotkey": "Passive", "sort": "1"}],
            },
        },
    )

    repo = HeroesProfileRepository(data_root=tmp_path)

    heroes = repo.list_talent_build_heroes()
    assert [hero.slug for hero in heroes] == ["thelostvikings"]
    assert heroes[0].export_token == "LostVikings"

    build = repo.get_talent_build("The Lost Vikings")
    assert build is not None
    assert build.hero.export_token == "LostVikings"
    assert build.tiers[0].level == "1"
    assert [option.index for option in build.tiers[0].options] == [1, 2]
    assert build.tiers[0].options[1].title == "Spy Games"
    assert build.tiers[-1].level == "20"
    assert build.tiers[-1].options == []


def test_talent_string_converter_uses_build_copy_name_and_zero_placeholders():
    hero_record = {
        "name": "The Lost Vikings",
        "slug": "thelostvikings",
        "build_copy_name": "LostVikings",
    }

    assert resolve_hero_token(hero_record) == "LostVikings"
    assert build_talent_string("Leoric", {"1": 3, "4": 2, "7": 1, "10": 1, "13": 2, "16": 2, "20": 1}) == "[T3211221,Leoric]"
    assert build_talent_string_for_hero(hero_record, {"1": 1, "4": 1, "7": 2, "10": 2, "13": 2}) == "[T1122200,LostVikings]"
