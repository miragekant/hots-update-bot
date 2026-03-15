from __future__ import annotations

import json
from pathlib import Path

import heroesprofile.update_data as upd


def test_parse_only_datasets_defaults_and_dedupes():
    assert upd.parse_only_datasets(None) == ["patches", "heroes", "maps", "talents"]
    assert upd.parse_only_datasets("heroes,patches,heroes") == ["heroes", "patches"]


def test_update_heroesprofile_data_writes_expected_structure(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(upd, "fetch_patches", lambda: {"2.55": ["2.55.15.96477", "2.55.14.95918"]})
    monkeypatch.setattr(
        upd,
        "fetch_heroes",
        lambda: {
            "Abathur": {
                "id": 1,
                "name": "Abathur",
                "short_name": "abathur",
                "alt_name": None,
                "role": "Specialist",
                "new_role": "Support",
                "type": "Melee",
                "release_date": "2014-03-13 00:00:01",
                "rework_date": None,
                "last_change_patch_version": "2.55.4.91769",
                "build_copy_name": "Abathur",
                "last_updated": "2024-02-06 18:32:51",
                "translations": ["abathur", "абатур"],
            }
        },
    )
    monkeypatch.setattr(
        upd,
        "fetch_maps",
        lambda: [
            {"map_id": 1, "name": "Cursed Hollow", "short_name": "CursedHollow", "type": "standard", "ranked_rotation": 1, "playable": 1}
        ],
    )
    monkeypatch.setattr(
        upd,
        "fetch_hero_talents",
        lambda hero_name: {
            hero_name: [
                {
                    "talent_id": 2423,
                    "title": "Pressurized Glands",
                    "description": "Increase range.",
                    "hotkey": "W",
                    "cooldown": "",
                    "mana_cost": "",
                    "sort": "1",
                    "icon": "storm_ui_icon_abathur_spikeburst.png",
                    "status": "playable",
                    "level": 1,
                }
            ]
        },
    )

    stats = upd.update_heroesprofile_data(data_root=tmp_path, workers=1)
    assert stats.patch_families == 1
    assert stats.heroes == 1
    assert stats.maps == 1
    assert stats.talent_heroes == 1
    assert stats.failed_talents == 0

    manifest = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["counts"]["heroes"] == 1

    hero_index = json.loads((tmp_path / "heroes" / "index.json").read_text(encoding="utf-8"))
    assert hero_index["heroes"][0]["slug"] == "abathur"

    hero_detail = json.loads((tmp_path / "heroes" / "by_name" / "abathur.json").read_text(encoding="utf-8"))
    assert "абатур" in hero_detail["aliases"]

    talents = json.loads((tmp_path / "talents" / "by_hero" / "abathur.json").read_text(encoding="utf-8"))
    assert talents["levels"] == ["1"]
    assert talents["talents_by_level"]["1"][0]["title"] == "Pressurized Glands"


def test_update_heroesprofile_data_uses_cached_heroes_for_talents(monkeypatch, tmp_path: Path):
    (tmp_path / "heroes").mkdir(parents=True, exist_ok=True)
    (tmp_path / "heroes" / "index.json").write_text(
        json.dumps(
            {
                "heroes": [
                    {
                        "name": "Abathur",
                        "slug": "abathur",
                        "aliases": ["Abathur"],
                        "file_path": "heroesprofile/heroes/by_name/abathur.json",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        upd,
        "fetch_hero_talents",
        lambda hero_name: {hero_name: [{"talent_id": 1, "title": "A", "description": "B", "level": 1, "sort": "1"}]},
    )

    stats = upd.update_heroesprofile_data(data_root=tmp_path, datasets=["talents"], workers=1)
    assert stats.talent_heroes == 1
    assert stats.failed_talents == 0
    assert (tmp_path / "talents" / "by_hero" / "abathur.json").exists()
