from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from heroesprofile.update_data import normalize_lookup_key


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

    def get_hero(self, name: str) -> dict[str, Any] | None:
        hero = self._hero_index().get(normalize_lookup_key(name))
        if hero is None:
            return None
        file_path = hero.get("file_path")
        if not isinstance(file_path, str) or not file_path.strip():
            return None
        path = Path(file_path)
        if not path.is_absolute():
            path = self.data_root / path
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def get_hero_talents(self, hero_slug: str) -> dict[str, Any] | None:
        path = self.data_root / "talents" / "by_hero" / f"{hero_slug}.json"
        if not path.exists():
            return None
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else None

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
