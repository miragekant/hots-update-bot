# HeroesProfile General API Discord Integration Plan

## Summary
Add a cache-first HeroesProfile integration that stores patch, map, hero, and hero talent data locally, then exposes a focused Discord command set: `/hero`, `/map`, and `/patch`.

## Implementation Changes
- Add a reusable updater at `heroesprofile/update_data.py`.
- Store normalized data under `heroesprofile/patches/`, `heroesprofile/maps/`, `heroesprofile/heroes/`, and `heroesprofile/talents/`.
- Add a local repository for cache reads and normalized name lookup.
- Add Discord commands for hero, map, and patch views using rich embeds and button pagination where needed.
- Keep command handling local-cache-only; users should never fetch live HeroesProfile data on demand.

## Public Interfaces
- CLI:
  - `python heroesprofile/update_data.py`
  - `python heroesprofile/update_data.py --only heroes,talents`
- Slash commands:
  - `/hero`
  - `/map`
  - `/patch`

## Test Plan
- Updater tests for normalized writes, manifest creation, and talents-by-hero generation.
- Repository tests for alias/translation hero lookups plus map and patch resolution.
- Bot formatter and pagination tests for hero and patch embeds.

## Assumptions
- The `openApi` General endpoints remain public and stable.
- `Heroes/Talents` is fetched once per hero using the cached hero list as input.
- Manual updater execution is sufficient for v1.
