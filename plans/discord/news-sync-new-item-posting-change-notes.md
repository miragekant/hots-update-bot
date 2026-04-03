# News Sync New-Item Posting Change Notes

## Summary
- Scheduled daily syncs now announce each newly discovered HOTS article in Discord after the sync summary.
- Update-only runs no longer post an article embed.
- Scheduled posts still read from the local cache only.

## Behavior
- If `update_news()` returns `new > 0`, the bot sends:
  - the existing summary message with sync counts
  - one article message per newly added article
- New article messages are posted oldest-to-newest within the batch.
- If a newly added article cannot be loaded from local cache, the bot logs a warning and continues with the remaining items.

## Internal Contract
- `news.update_news.UpdateStats` now includes `new_news_ids: list[str]`.
- `new_news_ids` contains only articles that were newly inserted during that updater run.

## Tests
- Updater tests cover:
  - new-item runs returning `new_news_ids`
  - update-only runs returning no new IDs
  - multiple new items preserving updater discovery order in `new_news_ids`
- Bot schedule tests cover:
  - summary plus per-new-item posts
  - update-only runs skipping article posts
  - missing channel handling
  - missing cached article handling
