# GCP Secret Manager Support Plan

## Goal
- Allow the Discord bot to load runtime configuration either from local environment variables or from Google Cloud Secret Manager.
- Keep bot command behavior unchanged: command reads still use only local cache files.

## Scope
- Add a config source switch via `BOT_CONFIG_SOURCE`.
- Support `env` as the default source.
- Support `gcp` by reading named secrets from Secret Manager using `GCP_PROJECT_ID`.
- Preserve existing validation and default handling for the daily schedule fields.

## Secret Names
- `BOT_TOKEN`
- `GUILD_ID`
- `NEWS_CHANNEL_ID`
- `DAILY_UPDATE_UTC_HOUR`
- `DAILY_UPDATE_UTC_MINUTE`

## Implementation Steps
1. Refactor config loading into source-specific helpers.
2. Add a Secret Manager client factory with a clear error if the dependency is missing.
3. Read required bot values from Secret Manager and treat missing optional schedule secrets as defaults.
4. Reuse the existing validation path so both config sources enforce the same integer parsing and bounds checks.
5. Add tests for `env`, `gcp`, missing `GCP_PROJECT_ID`, and invalid source handling.
6. Document the new runtime configuration path and add the dependency to `requirements.txt`.

## Non-Goals
- No user-triggered cloud fetches.
- No changes to the news cache format.
- No deployment automation for Cloud Run, Cloud Build, or Terraform in this change.
