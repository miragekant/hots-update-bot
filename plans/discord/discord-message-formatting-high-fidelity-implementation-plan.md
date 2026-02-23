# Discord Message Formatting High-Fidelity Plan (Implemented)

## Summary
Improve Discord article rendering so cached HTML body content preserves structure similar to original article layout, while staying compact to reduce number of message chunks.

## Implemented Outcome
- Replaced flat text extraction with structured HTML-to-Discord markdown rendering.
- Added compact, high-fidelity mapping for headings, lists, links, emphasis, blockquotes, code blocks, horizontal rules, and images.
- Added markdown-aware chunk splitting with Discord-safe length limits.
- Kept command behavior unchanged (`/latest`, `/news`), but improved body readability and compactness.

## Design and Changes

### 1. Rendering Pipeline (`bot/message.py`)
Implemented a new pipeline centered on:
- `render_html_to_discord_markdown(html: str, compact: bool = True) -> str`
- `split_markdown_chunks(text: str, max_chars: int = 1900) -> list[str]`

`format_article_body_chunks(...)` now uses this pipeline directly.

### 2. HTML to Markdown Mapping Rules
- `h1/h2` -> `## ...`
- `h3/h4` -> `### ...`
- `h5/h6` -> `**...**`
- `p/div/section/article` -> normalized paragraph text
- `strong/b`, `em/i`, `u`, `s/strike/del` -> Discord markdown emphasis
- `a[href]` -> `[text](url)` or URL fallback
- `ul/ol` (including nesting) -> compact bullet/numbered list output
- `blockquote` -> `> ...`
- `pre/code` -> fenced code blocks
- `hr` -> `---`
- `img` -> `![alt](src)` style token

### 3. Compactness Strategy
- Tight block spacing to reduce output size.
- Preserved hierarchy without unnecessary blank lines.
- Compact mode remains default in runtime formatting.

### 4. Chunking Strategy
- Block-aware splitting rather than naive text slicing.
- Preserves markdown boundaries as much as possible.
- Handles overlong blocks via controlled splitting.
- Enforces max length per message (`<= 1900`).
- Returns non-empty chunks only.

## Public Interfaces / API Impact
- Added in `bot/message.py`:
  - `render_html_to_discord_markdown(...)`
  - `split_markdown_chunks(...)`
- Backward-compatible wrappers retained:
  - `html_to_discord_text(...)`
  - `split_text_chunks(...)`
- Existing command interfaces unchanged.

## Tests Implemented
Updated `tests/test_bot_message.py` with coverage for:
1. heading + paragraph rendering
2. nested list rendering
3. link markdown conversion
4. blockquote + emphasis rendering
5. fenced code block rendering
6. chunk max-length guarantees
7. non-empty chunk guarantees
8. compact-vs-noncompact size comparison
9. existing news list embed footer behavior

## Validation
- Ran targeted formatter tests successfully.
- Ran full test suite successfully.
- Current status: all tests passing.

## Documentation
Updated `README.md` to note that article body rendering now maps HTML structure into compact Discord markdown.

## Assumptions and Defaults
- Compact mode is default for Discord delivery.
- Chunking limit remains conservative at `1900` chars.
- No changes to news crawler schema or storage.
- Existing slash commands and scheduler flow remain unchanged.
