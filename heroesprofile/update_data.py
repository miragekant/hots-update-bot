from __future__ import annotations

import argparse
import json
import logging
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any
from urllib.parse import quote

import requests

BASE_URL = "https://api.heroesprofile.com/openApi"
PATCHES_URL = f"{BASE_URL}/Patches"
HEROES_URL = f"{BASE_URL}/Heroes"
MAPS_URL = f"{BASE_URL}/Maps"
TALENTS_URL = f"{BASE_URL}/Heroes/Talents"
REQUEST_TIMEOUT = 30
MAX_RETRIES = 3
DEFAULT_DATA_ROOT = Path("heroesprofile")
DEFAULT_WORKERS = 8
VALID_DATASETS = {"patches", "heroes", "maps", "talents"}

logger = logging.getLogger("heroesprofile_update")


@dataclass
class UpdateStats:
    generated_at: str
    datasets: list[str]
    patch_families: int = 0
    heroes: int = 0
    maps: int = 0
    talent_heroes: int = 0
    failed_talents: int = 0


def configure_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logger.setLevel(level)
    logger.handlers.clear()
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(level)
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(handler)
    logger.propagate = False


def parse_cli_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Update HeroesProfile data cache")
    parser.add_argument(
        "--only",
        type=str,
        default=None,
        help="comma-separated dataset names: patches,heroes,maps,talents",
    )
    parser.add_argument("--workers", type=int, default=DEFAULT_WORKERS, help="talent fetch worker count")
    parser.add_argument("--verbose", action="store_true", help="enable debug logging")
    return parser.parse_args()


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize_lookup_key(value: str | None) -> str:
    if not value:
        return ""
    normalized = value.casefold().strip()
    normalized = normalized.replace("’", "'").replace("`", "'")
    return re.sub(r"[\W_]+", "", normalized, flags=re.UNICODE)


def slugify(value: str | None) -> str:
    raw = (value or "").strip().lower()
    raw = raw.replace("’", "'").replace("`", "'")
    raw = re.sub(r"[^a-z0-9]+", "-", raw)
    return raw.strip("-") or "unknown"


def _request_json(url: str) -> Any:
    last_error: Exception | None = None
    for attempt in range(MAX_RETRIES):
        try:
            response = requests.get(url, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as exc:
            last_error = exc
            logger.warning("request failed (%s/%s) url=%s error=%s", attempt + 1, MAX_RETRIES, url, exc)
            if attempt < MAX_RETRIES - 1:
                time.sleep(0.5 * (attempt + 1))
    assert last_error is not None
    raise last_error


def fetch_patches() -> dict[str, list[str]]:
    payload = _request_json(PATCHES_URL)
    if not isinstance(payload, dict):
        raise ValueError("patches payload must be a JSON object")
    return payload


def fetch_heroes() -> dict[str, dict[str, Any]]:
    payload = _request_json(HEROES_URL)
    if not isinstance(payload, dict):
        raise ValueError("heroes payload must be a JSON object")
    return payload


def fetch_maps() -> list[dict[str, Any]]:
    payload = _request_json(MAPS_URL)
    if not isinstance(payload, list):
        raise ValueError("maps payload must be a JSON array")
    return payload


def fetch_hero_talents(hero_name: str) -> dict[str, Any]:
    payload = _request_json(f"{TALENTS_URL}?hero={quote(hero_name)}")
    if not isinstance(payload, dict):
        raise ValueError("talents payload must be a JSON object")
    return payload


def normalize_patch_payload(payload: dict[str, list[str]]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for family in sorted(payload.keys(), reverse=True):
        builds = payload.get(family) or []
        if not isinstance(builds, list):
            continue
        normalized_builds = [str(build) for build in builds]
        records.append(
            {
                "version_family": str(family),
                "builds": normalized_builds,
                "build_count": len(normalized_builds),
            }
        )
    return records


def _hero_aliases(hero: dict[str, Any]) -> list[str]:
    aliases: list[str] = []
    for key in ("name", "short_name", "alt_name", "build_copy_name"):
        value = hero.get(key)
        if isinstance(value, str) and value.strip():
            aliases.append(value.strip())
    for value in hero.get("translations") or []:
        if isinstance(value, str) and value.strip():
            aliases.append(value.strip())
    seen: set[str] = set()
    unique: list[str] = []
    for value in aliases:
        marker = normalize_lookup_key(value)
        if not marker or marker in seen:
            continue
        seen.add(marker)
        unique.append(value)
    return unique


def normalize_heroes_payload(payload: dict[str, dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    summaries: list[dict[str, Any]] = []
    full_records: list[dict[str, Any]] = []
    for hero_name in sorted(payload.keys()):
        raw = payload.get(hero_name) or {}
        if not isinstance(raw, dict):
            continue
        canonical_name = str(raw.get("name") or hero_name)
        short_name = str(raw.get("short_name") or canonical_name)
        slug = slugify(short_name)
        aliases = _hero_aliases(raw)
        summary = {
            "id": raw.get("id"),
            "name": canonical_name,
            "slug": slug,
            "short_name": raw.get("short_name"),
            "alt_name": raw.get("alt_name"),
            "role": raw.get("role"),
            "new_role": raw.get("new_role"),
            "type": raw.get("type"),
            "release_date": raw.get("release_date"),
            "rework_date": raw.get("rework_date"),
            "last_change_patch_version": raw.get("last_change_patch_version"),
            "last_updated": raw.get("last_updated"),
            "aliases": aliases,
            "file_path": f"heroes/by_name/{slug}.json",
        }
        full_record = dict(raw)
        full_record["name"] = canonical_name
        full_record["slug"] = slug
        full_record["aliases"] = aliases
        full_record["file_path"] = summary["file_path"]
        summaries.append(summary)
        full_records.append(full_record)

    summaries.sort(key=lambda item: str(item.get("name") or ""))
    full_records.sort(key=lambda item: str(item.get("name") or ""))
    return summaries, full_records


def normalize_maps_payload(payload: list[dict[str, Any]]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for raw in payload:
        if not isinstance(raw, dict):
            continue
        name = str(raw.get("name") or "")
        if not name:
            continue
        short_name = raw.get("short_name")
        aliases = [name]
        if isinstance(short_name, str) and short_name.strip():
            aliases.append(short_name.strip())
        raw = dict(raw)
        raw["aliases"] = aliases
        records.append(raw)
    return sorted(records, key=lambda item: str(item.get("name") or ""))


def normalize_talents_payload(hero: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    hero_name = str(hero.get("name") or "")
    raw_talents = payload.get(hero_name)
    if not isinstance(raw_talents, list):
        values = list(payload.values())
        raw_talents = values[0] if values else []

    talents_by_level: dict[str, list[dict[str, Any]]] = {}
    for raw in raw_talents:
        if not isinstance(raw, dict):
            continue
        level = str(raw.get("level") or "unknown")
        item = {
            "talent_id": raw.get("talent_id"),
            "title": raw.get("title"),
            "description": raw.get("description"),
            "hotkey": raw.get("hotkey"),
            "cooldown": raw.get("cooldown"),
            "mana_cost": raw.get("mana_cost"),
            "sort": raw.get("sort"),
            "icon": raw.get("icon"),
            "status": raw.get("status"),
        }
        talents_by_level.setdefault(level, []).append(item)

    for level, items in talents_by_level.items():
        items.sort(key=lambda item: (str(item.get("sort") or ""), str(item.get("title") or "")))

    ordered_levels = sorted(talents_by_level.keys(), key=lambda value: (value == "unknown", int(value) if value.isdigit() else 999))
    return {
        "hero_name": hero_name,
        "hero_slug": hero.get("slug"),
        "talent_count": sum(len(items) for items in talents_by_level.values()),
        "levels": ordered_levels,
        "talents_by_level": talents_by_level,
    }


def atomic_write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        temp_path = Path(handle.name)
        json.dump(data, handle, ensure_ascii=False, indent=2, sort_keys=False)
        handle.write("\n")
    temp_path.replace(path)


def parse_only_datasets(raw_value: str | None) -> list[str]:
    if raw_value is None or raw_value.strip() == "":
        return ["patches", "heroes", "maps", "talents"]
    values = [part.strip().lower() for part in raw_value.split(",") if part.strip()]
    unknown = [value for value in values if value not in VALID_DATASETS]
    if unknown:
        raise ValueError(f"unknown dataset(s): {', '.join(unknown)}")
    deduped: list[str] = []
    for value in values:
        if value not in deduped:
            deduped.append(value)
    return deduped


def _heroes_index_path(data_root: Path) -> Path:
    return data_root / "heroes" / "index.json"


def _load_cached_hero_summaries(data_root: Path) -> list[dict[str, Any]]:
    path = _heroes_index_path(data_root)
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    heroes = payload.get("heroes") if isinstance(payload, dict) else None
    return heroes if isinstance(heroes, list) else []


def _hero_summaries_for_talents(data_root: Path, current: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    if current:
        return current
    cached = _load_cached_hero_summaries(data_root)
    if cached:
        return cached
    logger.info("hero cache missing; fetching heroes to resolve talents")
    summaries, full_records = normalize_heroes_payload(fetch_heroes())
    write_heroes_data(data_root, summaries, full_records)
    return summaries


def write_patches_data(data_root: Path, records: list[dict[str, Any]]) -> None:
    atomic_write_json(data_root / "patches" / "index.json", {"patches": records})


def write_heroes_data(data_root: Path, summaries: list[dict[str, Any]], full_records: list[dict[str, Any]]) -> None:
    atomic_write_json(_heroes_index_path(data_root), {"heroes": summaries})
    for hero in full_records:
        atomic_write_json(data_root / "heroes" / "by_name" / f"{hero['slug']}.json", hero)


def write_maps_data(data_root: Path, records: list[dict[str, Any]]) -> None:
    atomic_write_json(data_root / "maps" / "index.json", {"maps": records})


def write_talents_data(data_root: Path, hero_slug: str, payload: dict[str, Any]) -> None:
    atomic_write_json(data_root / "talents" / "by_hero" / f"{hero_slug}.json", payload)


def build_manifest(data_root: Path, stats: UpdateStats) -> dict[str, Any]:
    return {
        "generated_at": stats.generated_at,
        "datasets": stats.datasets,
        "counts": {
            "patch_families": stats.patch_families,
            "heroes": stats.heroes,
            "maps": stats.maps,
            "talent_heroes": stats.talent_heroes,
            "failed_talents": stats.failed_talents,
        },
        "paths": {
            "patches": str(data_root / "patches" / "index.json"),
            "heroes": str(_heroes_index_path(data_root)),
            "maps": str(data_root / "maps" / "index.json"),
            "talents": str(data_root / "talents" / "by_hero"),
        },
        "sources": {
            "patches": PATCHES_URL,
            "heroes": HEROES_URL,
            "maps": MAPS_URL,
            "talents": TALENTS_URL,
        },
    }


def update_heroesprofile_data(
    *,
    data_root: Path = DEFAULT_DATA_ROOT,
    datasets: list[str] | None = None,
    workers: int = DEFAULT_WORKERS,
) -> UpdateStats:
    selected = datasets or ["patches", "heroes", "maps", "talents"]
    generated_at = now_utc_iso()
    stats = UpdateStats(generated_at=generated_at, datasets=selected)
    hero_summaries: list[dict[str, Any]] = []

    logger.info("starting HeroesProfile update datasets=%s", ",".join(selected))

    if "patches" in selected:
        patch_records = normalize_patch_payload(fetch_patches())
        write_patches_data(data_root, patch_records)
        stats.patch_families = len(patch_records)
        logger.info("stored patch families=%s", stats.patch_families)

    if "heroes" in selected:
        hero_summaries, hero_full_records = normalize_heroes_payload(fetch_heroes())
        write_heroes_data(data_root, hero_summaries, hero_full_records)
        stats.heroes = len(hero_summaries)
        logger.info("stored heroes=%s", stats.heroes)
    else:
        hero_summaries = _load_cached_hero_summaries(data_root)
        stats.heroes = len(hero_summaries)

    if "maps" in selected:
        maps = normalize_maps_payload(fetch_maps())
        write_maps_data(data_root, maps)
        stats.maps = len(maps)
        logger.info("stored maps=%s", stats.maps)

    if "talents" in selected:
        hero_summaries = _hero_summaries_for_talents(data_root, hero_summaries)
        stats.heroes = max(stats.heroes, len(hero_summaries))
        talent_count = 0
        failures = 0
        max_workers = max(1, workers)
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_map = {
                executor.submit(fetch_hero_talents, str(hero.get("name") or "")): hero
                for hero in hero_summaries
                if str(hero.get("name") or "").strip()
            }
            for future in as_completed(future_map):
                hero = future_map[future]
                hero_name = str(hero.get("name") or "")
                hero_slug = str(hero.get("slug") or slugify(hero_name))
                try:
                    payload = normalize_talents_payload(hero, future.result())
                except Exception as exc:
                    failures += 1
                    logger.error("failed to fetch talents hero=%s error=%s", hero_name, exc)
                    continue
                write_talents_data(data_root, hero_slug, payload)
                talent_count += 1
        stats.talent_heroes = talent_count
        stats.failed_talents = failures
        logger.info("stored talent payloads=%s failed=%s", talent_count, failures)

    atomic_write_json(data_root / "manifest.json", build_manifest(data_root, stats))
    logger.info("HeroesProfile update finished stats=%s", asdict(stats))
    return stats


def main() -> None:
    args = parse_cli_args()
    configure_logging(verbose=args.verbose)
    datasets = parse_only_datasets(args.only)
    stats = update_heroesprofile_data(datasets=datasets, workers=max(1, args.workers))
    print(json.dumps(asdict(stats), indent=2))


if __name__ == "__main__":
    main()
