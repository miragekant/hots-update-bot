# Rich Embed + Button Pagination Upgrade for Discord News Messages

## Summary
Upgrade Discord article delivery to use rich embeds with interaction buttons for page navigation, replacing current multi-follow-up chunk messages.

## Goals
- Keep `/news` list pagination with buttons and select.
- Add embed-based page controls for full article content.
- Apply the same article pagination experience to `/latest`.
- Preserve message size safety and existing crawler/index behavior.

## Planned Changes

### 1. Message Formatting
- Add helper to produce embed-sized article body pages from rendered markdown.
- Keep existing high-fidelity HTML-to-markdown renderer.
- Keep conservative per-page body size under embed description limits.

### 2. Pagination Views
- Keep `NewsPaginationView` for list pages.
- Add `ArticlePaginationView` for article body pages with:
  - `Prev` button
  - `Next` button
  - optional `Open Original` URL button
- Restrict interactions to requester for command-invoked views.
- Allow open interactions for scheduled channel posts if needed.

### 3. Command Flow Updates
- `/latest`: send one paginated embed message instead of multiple follow-ups.
- `/news` select action: open selected article in a new paginated embed message.
- Daily updater post path can reuse the same article pagination view.

### 4. Tests
- Add unit tests for embed-page body splitting helper.
- Add pagination tests for `ArticlePaginationView` state transitions and button enabled/disabled behavior.
- Ensure existing tests remain green.

## Acceptance Criteria
- Long articles are navigable by buttons within one message.
- No article page exceeds message/embed limits.
- `/latest` and `/news` article-open behavior are consistent.
- Full test suite passes.

## Assumptions
- Buttons are preferred interaction model for article paging.
- Existing slash commands and local repository APIs remain unchanged.
