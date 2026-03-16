# Optional List Mode for `/hero`, `/map`, and `/patch`

## Summary
- Make `/hero`, `/map`, and `/patch` accept an optional lookup argument.
- Keep the current detail view unchanged when the argument is provided.
- When the argument is omitted, show a paginated browse view with concise summaries and a select menu that opens the existing detail view for the chosen item.

## Implementation Changes
- Add cache-backed list accessors in `HeroesProfileRepository` for heroes, maps, and patch families.
- Add embed formatters for hero, map, and patch list pages with short summaries and `Page X/Y` footers.
- Add a reusable HeroesProfile list pagination view with Prev/Next buttons, requester-only interaction checks, and a per-page select menu.
- Update the three slash commands to branch between detail mode and list mode based on whether the argument is present.

## Test Plan
- Repository tests for the new list accessors.
- Message tests for hero, map, and patch list embed summaries.
- Pagination tests for page navigation, select options, requester-only controls, and detail loading.

## Assumptions
- Cache index order is the intended browse order.
- Patch index `builds[0]` is the newest build when present.
- Reusing the `/news` browse interaction pattern is the intended UX for list mode.
