from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from bot.talent_builder import TalentBuildData, TalentBuildHero, TalentBuildTier, TalentBuildTierOption, resolve_hero_token
from heroesprofile.update_data import normalize_lookup_key

DEFAULT_BUILD_LEVELS = ["1", "4", "7", "10", "13", "16", "20"]


@dataclass
class HeroesProfileRepository:
    data_root: Path = Path("heroesprofile")

    def _read_json(self, path: Path, default: dict[str, Any]) -> dict[str, Any]:
        if not path.exists():
            return default
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else default

    def manifest(self) -> dict[str, Any]:
        return self._read_json(self.data_root / "manifest.json", {})

    def has_data(self) -> bool:
        return (self.data_root / "manifest.json").exists()

    def hero_summaries(self) -> list[dict[str, Any]]:
        payload = self._read_json(self.data_root / "heroes" / "index.json", {"heroes": []})
        heroes = payload.get("heroes")
        return heroes if isinstance(heroes, list) else []

    def _hero_index(self) -> dict[str, dict[str, Any]]:
        index: dict[str, dict[str, Any]] = {}
        for hero in self.hero_summaries():
            keys = [hero.get("name"), hero.get("short_name"), hero.get("alt_name")]
            keys.extend(hero.get("aliases") or [])
            for key in keys:
                marker = normalize_lookup_key(str(key or ""))
                if marker and marker not in index:
                    index[marker] = hero
        return index

    def _read_hero_from_summary(self, hero_summary: dict[str, Any]) -> dict[str, Any] | None:
        file_path = hero_summary.get("file_path")
        if not isinstance(file_path, str) or not file_path.strip():
            return None
        path = Path(file_path)
        if not path.is_absolute():
            path = self.data_root / path
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def get_hero(self, name: str) -> dict[str, Any] | None:
        hero = self._hero_index().get(normalize_lookup_key(name))
        if hero is None:
            return None
        return self._read_hero_from_summary(hero)

    def get_hero_by_slug(self, hero_slug: str) -> dict[str, Any] | None:
        wanted = str(hero_slug or "").strip().lower()
        if not wanted:
            return None
        for hero in self.hero_summaries():
            if str(hero.get("slug") or "").strip().lower() == wanted:
                return self._read_hero_from_summary(hero)
        return None

    def get_hero_talents(self, hero_slug: str) -> dict[str, Any] | None:
        path = self.data_root / "talents" / "by_hero" / f"{hero_slug}.json"
        if not path.exists():
            return None
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else None

    def list_talent_build_heroes(self) -> list[TalentBuildHero]:
        records: list[TalentBuildHero] = []
        for hero in self.hero_summaries():
            slug = str(hero.get("slug") or "").strip()
            if not slug or self.get_hero_talents(slug) is None:
                continue
            full_record = self._read_hero_from_summary(hero)
            if full_record is None:
                continue
            records.append(
                TalentBuildHero(
                    slug=slug,
                    name=str(hero.get("name") or "Unknown Hero"),
                    export_token=resolve_hero_token(full_record),
                )
            )
        return sorted(records, key=lambda item: normalize_lookup_key(item.name))

    def list_talent_builder_heroes(self) -> list[dict[str, Any]]:
        return [
            {
                "slug": hero.slug,
                "name": hero.name,
                "build_copy_name": hero.export_token,
                "aliases": [],
            }
            for hero in self.list_talent_build_heroes()
        ]

    def get_talent_build(self, hero_name_or_slug: str) -> TalentBuildData | None:
        hero_record = self.get_hero(hero_name_or_slug)
        if hero_record is None:
            hero_record = self.get_hero_by_slug(hero_name_or_slug)
        if hero_record is None:
            return None

        hero_slug = str(hero_record.get("slug") or "").strip()
        if not hero_slug:
            return None
        talent_payload = self.get_hero_talents(hero_slug)
        if not talent_payload:
            return None

        found_levels = [str(level) for level in talent_payload.get("levels") or []]
        levels = list(dict.fromkeys([*DEFAULT_BUILD_LEVELS, *found_levels]))
        talents_by_level = talent_payload.get("talents_by_level") or {}
        tiers: list[TalentBuildTier] = []
        for level in levels:
            raw_items = talents_by_level.get(level) or []
            options: list[TalentBuildTierOption] = []
            for index, raw_item in enumerate(raw_items, start=1):
                if not isinstance(raw_item, dict):
                    continue
                options.append(
                    TalentBuildTierOption(
                        index=index,
                        title=str(raw_item.get("title") or f"Talent {index}"),
                        description=str(raw_item.get("description") or "").strip(),
                        hotkey=str(raw_item.get("hotkey") or "").strip(),
                    )
                )
            tiers.append(TalentBuildTier(level=level, options=options))

        return TalentBuildData(
            hero=TalentBuildHero(
                slug=hero_slug,
                name=str(hero_record.get("name") or "Unknown Hero"),
                export_token=resolve_hero_token(hero_record),
            ),
            tiers=tiers,
        )

    def get_talent_builder_data(self, hero_slug: str) -> dict[str, Any] | None:
        build = self.get_talent_build(hero_slug)
        if build is None:
            return None
        options_by_level = {
            tier.level: [
                {
                    "option_index": option.index,
                    "title": option.title,
                    "description": option.description,
                    "hotkey": option.hotkey,
                }
                for option in tier.options
            ]
            for tier in build.tiers
        }
        hero_record = self.get_hero_by_slug(build.hero.slug)
        if hero_record is None:
            return None
        return {
            "hero": hero_record,
            "levels": [tier.level for tier in build.tiers],
            "options_by_level": options_by_level,
        }

    def maps(self) -> list[dict[str, Any]]:
        payload = self._read_json(self.data_root / "maps" / "index.json", {"maps": []})
        maps = payload.get("maps")
        return maps if isinstance(maps, list) else []

    def get_map(self, name: str) -> dict[str, Any] | None:
        marker = normalize_lookup_key(name)
        for item in self.maps():
            keys = [item.get("name"), item.get("short_name")]
            keys.extend(item.get("aliases") or [])
            if marker in {normalize_lookup_key(str(key or "")) for key in keys}:
                return item
        return None

    def patch_families(self) -> list[dict[str, Any]]:
        payload = self._read_json(self.data_root / "patches" / "index.json", {"patches": []})
        patches = payload.get("patches")
        return patches if isinstance(patches, list) else []

    def get_patch(self, version: str) -> dict[str, Any] | None:
        wanted = str(version or "").strip()
        if not wanted:
            return None
        for item in self.patch_families():
            family = str(item.get("version_family") or "")
            builds = [str(build) for build in item.get("builds") or []]
            if wanted == family or wanted in builds:
                match = dict(item)
                if wanted in builds and wanted != family:
                    match["matched_build"] = wanted
                return match
        return None
