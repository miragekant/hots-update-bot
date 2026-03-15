from __future__ import annotations

import json
from pathlib import Path

from bot.heroesprofile_repository import HeroesProfileRepository


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
