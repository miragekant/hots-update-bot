# Talent Builder Discord Feature Plan

## Summary
- Add a cache-first `/talentbuilder` slash command that lets a user privately assemble a hero build from local `heroesprofile/talents/by_hero/*.json` data.
- Let the user review and revise any tier, optionally name the build, and export the HOTS talent string in a copy-friendly code block.
- Keep command handling local-cache only and save this design record under `plans/discord/`.

## Key Changes
- Add a reusable talent-string module in `bot/` that converts ordered tier selections for levels `1,4,7,10,13,16,20` into `[T<digits>,<HeroToken>]`, using `0` for unset tiers.
- Resolve the exported hero token from cached hero metadata, preferring `build_copy_name` when present and falling back to a deterministic token rule.
- Extend the HeroesProfile repository with builder-oriented read APIs that expose:
  - heroes eligible for talent building
  - stable, sorted tier options per hero
  - the option indexes used for exported talent-string digits
- Add `/talentbuilder` in `bot/run.py` with an ephemeral interactive flow:
  - hero selection
  - editable tier board with jump controls
  - `Any talent`, `Finish`, and `Cancel` actions
  - optional build-name modal before export
- Return a summary embed plus a fenced code block with the talent string. Do not attempt direct clipboard access.

## Public Interfaces / Types
- Add a reusable converter API such as `build_talent_string(hero_token, selections) -> str`.
- Add a normalized tier-selection contract using ordered levels `["1", "4", "7", "10", "13", "16", "20"]`.
- Add repository helpers for listing eligible heroes and retrieving builder-ready talent option data for one hero.

## Test Plan
- Converter tests for full builds, partial builds with `0` placeholders, and hero token resolution.
- Repository tests for hero filtering and stable option ordering.
- Interaction tests for request ownership, tier changes, `Any talent`, finish flow, and clean handling of missing cache data.
- Verify final output remains within conservative Discord message sizing expectations.

## Assumptions
- No persistence is added in v1; each command invocation creates one in-memory draft.
- Talent-string digits are 1-based option indexes derived from cached `sort` order, with `0` reserved for `Any talent`.
- Use parallel agents during implementation:
  - one for repository/converter work
  - one for Discord interaction/view work
  - the main agent for integration, documentation, and verification
