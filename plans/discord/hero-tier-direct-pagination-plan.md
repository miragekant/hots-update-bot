# Hero Tier Direct Pagination Plan

## Summary
- Replace `/hero`'s use of the generic embed paginator with a hero-specific view that uses direct navigation buttons only.
- Keep all other commands on the existing `Prev` / `Next` paginator.
- Support tier overflow by exposing a separate direct target for each overflow page.

## Key Changes
- Add a hero page metadata helper that returns both hero embeds and the direct-button labels/page indexes for `Summary` and each tier page.
- Add a dedicated hero pagination view with requester-only interaction checks and one button per hero page target.
- Update `/hero` to use the new hero-specific pagination view.

## Tests
- Verify hero formatting still produces a summary page first.
- Verify overflow tiers produce stable direct-button labels such as `Level 1 (2/2)`.
- Verify the hero view disables the active page button and updates the embed when another page button is pressed.
- Verify non-requesting users are blocked from interacting with the hero paginator.

## Assumptions
- Verbose labels are preferred for hero tier buttons.
- Direct buttons are sufficient for `/hero`; sequential buttons are not needed there.
- Expected hero page counts stay well below Discord's 25-component view limit.
