from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

import discord
from bs4 import BeautifulSoup
from bs4.element import NavigableString, Tag

MAX_SAFE_MESSAGE_CHARS = 1900
MAX_EMBED_DESCRIPTION_CHARS = 3500


def _parse_iso_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None


def _format_timestamp_label(value: str | None) -> str:
    dt = _parse_iso_datetime(value)
    if dt is None:
        return "Unknown"
    return dt.strftime("%Y-%m-%d")


def _normalize_space(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _render_inline(node: NavigableString | Tag) -> str:
    if isinstance(node, NavigableString):
        return str(node)
    if not isinstance(node, Tag):
        return ""

    name = node.name.lower()
    if name == "br":
        return "\n"
    if name == "strong" or name == "b":
        return f"**{_normalize_space(_render_inline_children(node))}**"
    if name == "em" or name == "i":
        return f"*{_normalize_space(_render_inline_children(node))}*"
    if name == "u":
        return f"__{_normalize_space(_render_inline_children(node))}__"
    if name in {"s", "strike", "del"}:
        return f"~~{_normalize_space(_render_inline_children(node))}~~"
    if name == "code":
        return f"`{_normalize_space(node.get_text(' ', strip=True))}`"
    if name == "a":
        href = (node.get("href") or "").strip()
        text = _normalize_space(_render_inline_children(node))
        if href and text and text != href:
            return f"[{text}]({href})"
        return href or text
    if name == "img":
        src = (node.get("src") or "").strip()
        alt = _normalize_space(node.get("alt") or "") or "Image"
        if src:
            return f"![{alt}]({src})"
        return f"[{alt}]"

    return _render_inline_children(node)


def _render_inline_children(tag: Tag) -> str:
    return "".join(_render_inline(child) for child in tag.children)


def _render_list(list_tag: Tag, *, depth: int = 0, compact: bool = True) -> list[str]:
    ordered = list_tag.name.lower() == "ol"
    lines: list[str] = []
    index = 1
    for child in list_tag.children:
        if not isinstance(child, Tag) or child.name.lower() != "li":
            continue

        inline_parts: list[str] = []
        nested_blocks: list[list[str]] = []
        for li_child in child.children:
            if isinstance(li_child, Tag) and li_child.name.lower() in {"ul", "ol"}:
                nested_blocks.append(_render_list(li_child, depth=depth + 1, compact=compact))
            else:
                inline_parts.append(_render_inline(li_child))

        prefix = f"{index}. " if ordered else "- "
        base = _normalize_space("".join(inline_parts))
        indent = "  " * depth
        if base:
            lines.append(f"{indent}{prefix}{base}")
        else:
            lines.append(f"{indent}{prefix}".rstrip())

        for nested in nested_blocks:
            lines.extend(nested)

        if ordered:
            index += 1
    return lines


def _render_block(node: NavigableString | Tag, *, compact: bool = True) -> list[str]:
    if isinstance(node, NavigableString):
        text = _normalize_space(str(node))
        return [text] if text else []
    if not isinstance(node, Tag):
        return []

    name = node.name.lower()
    if name in {"h1", "h2"}:
        text = _normalize_space(_render_inline_children(node))
        return [f"## {text}"] if text else []
    if name in {"h3", "h4"}:
        text = _normalize_space(_render_inline_children(node))
        return [f"### {text}"] if text else []
    if name in {"h5", "h6"}:
        text = _normalize_space(_render_inline_children(node))
        return [f"**{text}**"] if text else []
    if name in {"p", "div", "section", "article"}:
        text = _normalize_space(_render_inline_children(node))
        return [text] if text else []
    if name in {"ul", "ol"}:
        lines = _render_list(node, compact=compact)
        return ["\n".join(lines)] if lines else []
    if name == "blockquote":
        inner_blocks = _render_blocks(node.children, compact=compact)
        if not inner_blocks:
            return []
        joined = "\n".join(inner_blocks)
        quoted = "\n".join(f"> {line}" if line.strip() else ">" for line in joined.splitlines())
        return [quoted]
    if name == "pre":
        code = node.get_text("\n", strip=False).strip("\n")
        return [f"```\n{code}\n```"] if code else []
    if name == "hr":
        return ["---"]
    if name == "img":
        return [_render_inline(node)]

    return _render_blocks(node.children, compact=compact)


def _render_blocks(nodes: Any, *, compact: bool = True) -> list[str]:
    blocks: list[str] = []
    for node in nodes:
        blocks.extend(_render_block(node, compact=compact))
    return [b for b in blocks if b and b.strip()]


def render_html_to_discord_markdown(html: str, *, compact: bool = True) -> str:
    soup = BeautifulSoup(html or "", "html.parser")
    blocks = _render_blocks(soup.children, compact=compact)
    if not blocks:
        return ""
    separator = "\n\n" if compact else "\n\n\n"
    rendered = separator.join(blocks)
    rendered = re.sub(r"\n{4,}", "\n\n\n", rendered)
    return rendered.strip()


def _split_blocks_preserving_fences(text: str) -> list[str]:
    lines = text.splitlines()
    blocks: list[str] = []
    current: list[str] = []
    in_fence = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("```"):
            in_fence = not in_fence
            current.append(line)
            continue
        if not in_fence and stripped == "":
            if current:
                blocks.append("\n".join(current).strip())
                current = []
            continue
        current.append(line)
    if current:
        blocks.append("\n".join(current).strip())
    return [b for b in blocks if b]


def _split_overlong_block(block: str, max_chars: int) -> list[str]:
    if len(block) <= max_chars:
        return [block]

    chunks: list[str] = []
    current: list[str] = []
    current_len = 0
    in_fence = False

    def flush() -> None:
        nonlocal current, current_len
        if not current:
            return
        text = "\n".join(current).strip()
        if in_fence and not text.rstrip().endswith("```"):
            text = f"{text}\n```"
        if text:
            chunks.append(text)
        current = ["```"] if in_fence else []
        current_len = len(current[0]) if current else 0

    for original_line in block.splitlines():
        line_parts = [original_line]
        if len(original_line) > max_chars:
            line_parts = [original_line[i : i + max_chars] for i in range(0, len(original_line), max_chars)]

        for line in line_parts:
            add_len = len(line) + (1 if current else 0)
            if current and (current_len + add_len > max_chars):
                flush()
            if not current:
                current = [line]
                current_len = len(line)
            else:
                current.append(line)
                current_len += add_len
            if line.strip().startswith("```"):
                in_fence = not in_fence

    if current:
        text = "\n".join(current).strip()
        if text:
            chunks.append(text)
    return [c for c in chunks if c]


def split_markdown_chunks(text: str, max_chars: int = MAX_SAFE_MESSAGE_CHARS) -> list[str]:
    if max_chars <= 0:
        raise ValueError("max_chars must be > 0")
    content = (text or "").strip()
    if content == "":
        return []
    if len(content) <= max_chars:
        return [content]

    chunks: list[str] = []
    blocks = _split_blocks_preserving_fences(content)
    current = ""
    for block in blocks:
        candidate = block if not current else f"{current}\n\n{block}"
        if len(candidate) <= max_chars:
            current = candidate
            continue
        if current:
            chunks.append(current)
            current = ""
        if len(block) <= max_chars:
            current = block
            continue
        for part in _split_overlong_block(block, max_chars):
            if len(part) <= max_chars:
                chunks.append(part)
    if current:
        chunks.append(current)
    return [c for c in chunks if c.strip()]


def html_to_discord_text(html: str) -> str:
    return render_html_to_discord_markdown(html, compact=True)


def split_text_chunks(text: str, max_chars: int = MAX_SAFE_MESSAGE_CHARS) -> list[str]:
    return split_markdown_chunks(text, max_chars=max_chars)


def format_article_embed(article_record: dict[str, Any]) -> discord.Embed:
    title = article_record.get("title") or "Untitled"
    raw_url = article_record.get("url")
    url = raw_url if isinstance(raw_url, str) and raw_url.strip() else None
    description = (article_record.get("description") or "").strip()
    if len(description) > MAX_EMBED_DESCRIPTION_CHARS:
        description = description[: MAX_EMBED_DESCRIPTION_CHARS - 3].rstrip() + "..."

    embed = discord.Embed(title=title, url=url, description=description or None)
    embed.add_field(name="Author", value=article_record.get("author") or "Unknown", inline=True)
    embed.add_field(name="Date", value=_format_timestamp_label(article_record.get("timestamp")), inline=True)
    embed.add_field(name="Section", value=article_record.get("section") or "latest", inline=True)

    header_image_url = article_record.get("header_image_url") or article_record.get("image_url")
    if isinstance(header_image_url, str) and header_image_url.strip():
        embed.set_image(url=header_image_url)

    return embed


def format_article_body_chunks(article_record: dict[str, Any], max_chars: int = MAX_SAFE_MESSAGE_CHARS) -> list[str]:
    body_text = render_html_to_discord_markdown(article_record.get("body_html") or "", compact=True)
    return split_markdown_chunks(body_text, max_chars=max_chars)


def format_article_body_embed_pages(
    article_record: dict[str, Any],
    max_chars: int = MAX_EMBED_DESCRIPTION_CHARS,
) -> list[str]:
    body_text = render_html_to_discord_markdown(article_record.get("body_html") or "", compact=True)
    pages = split_markdown_chunks(body_text, max_chars=max_chars)
    if not pages:
        return ["_No article body available._"]
    return pages


def format_news_list_embed(items: list[dict[str, Any]], page: int, total_pages: int, year_filter: int | None) -> discord.Embed:
    title = "HOTS News"
    if year_filter is not None:
        title = f"HOTS News ({year_filter})"
    embed = discord.Embed(title=title, description="Select an item below to view full details.")

    if not items:
        embed.add_field(name="No results", value="No local articles match this query.", inline=False)
    else:
        lines: list[str] = []
        for i, item in enumerate(items, start=1):
            item_title = item.get("title") or "Untitled"
            date_label = _format_timestamp_label(item.get("timestamp"))
            lines.append(f"{i}. **{item_title}** ({date_label})")
        embed.add_field(name="Articles", value="\n".join(lines), inline=False)

    embed.set_footer(text=f"Page {page}/{total_pages}")
    return embed
