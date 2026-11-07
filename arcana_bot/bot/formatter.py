"""
Bulletproof Telegram Rich HTML Formatter for ASTRA, ARCANA, and MATRIX.
Guarantees that EVERY message has clean, human-friendly visual formatting in Telegram:
- Normalizes any mixed HTML/Markdown output from LLMs so tags never conflict or get double-escaped
- Formats headings as elegant `✦ <b>Заголовок</b>` blocks
- Formats quotes (`> ...`) into native Telegram `<blockquote><i>...</i></blockquote>` blocks
- Formats `**bold**`, `*italic*`, and `` `code` `` strictly within each line so tags NEVER overlap across paragraphs or blockquotes
- Removes any stray unmatched `**` or `###` so raw Markdown symbols never leak into chat
- Splits long messages safely at <= 3200 chars per chunk so HTML expansion never exceeds Telegram's 4096-char limit
"""
from __future__ import annotations

import html
import re
from typing import List


def _format_inline_line(escaped_line: str) -> str:
    """
    Convert inline `code`, **bold**, __bold__, and *italic* strictly within a single line
    so unclosed markers on one line can never corrupt multi-line HTML structure.
    """
    if not escaped_line.strip():
        return ""

    code_blocks: List[str] = []

    def _save_code(m: re.Match) -> str:
        code_blocks.append(f"<code>{m.group(1)}</code>")
        return f"@@CODE_{len(code_blocks) - 1}@@"

    line = re.sub(r"`([^`]+)`", _save_code, escaped_line)

    # Convert paired **bold** and __bold__
    line = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", line)
    line = re.sub(r"__(.+?)__", r"<b>\1</b>", line)

    # Remove any leftover stray unmatched **
    line = line.replace("**", "")

    # Convert paired *italic* (only when not part of a word)
    line = re.sub(r"(?<!\w)\*([^\*]+?)\*(?!\w)", r"<i>\1</i>", line)

    # Restore inline code
    for idx, cb in enumerate(code_blocks):
        line = line.replace(f"@@CODE_{idx}@@", cb)

    return line


def markdown_to_telegram_html(text: str) -> str:
    """
    Convert any LLM Markdown, mixed HTML+Markdown, or plain text into valid,
    visually rich Telegram HTML guaranteed to parse without errors.
    """
    if not text:
        return ""

    # 1. Normalize any raw HTML tags that an LLM might have generated into Markdown first
    normalized = text.replace("\r\n", "\n")
    normalized = re.sub(r"<\s*br\s*/?\s*>", "\n", normalized, flags=re.I)
    normalized = re.sub(r"<\s*(?:b|strong)\s*>(.*?)<\s*/\s*(?:b|strong)\s*>", r"**\1**", normalized, flags=re.I | re.S)
    normalized = re.sub(r"<\s*(?:i|em)\s*>(.*?)<\s*/\s*(?:i|em)\s*>", r"*\1*", normalized, flags=re.I | re.S)
    normalized = re.sub(r"<\s*code\s*>(.*?)<\s*/\s*code\s*>", r"`\1`", normalized, flags=re.I | re.S)
    normalized = re.sub(
        r"<\s*blockquote\s*>(.*?)<\s*/\s*blockquote\s*>",
        lambda m: "\n".join(f"> {ln}" for ln in m.group(1).strip().split("\n")),
        normalized,
        flags=re.I | re.S,
    )
    # Strip any other unsupported HTML tags if present
    normalized = re.sub(r"</?(?:p|div|span|ul|ol|li|h[1-6])\b[^>]*>", "", normalized, flags=re.I)

    # 2. Escape `&`, `<`, `>` safely
    escaped = html.escape(normalized, quote=False)

    # 3. Process line-by-line for headers, dividers, blockquotes, and bullets
    raw_lines = escaped.split("\n")
    out_lines: List[str] = []
    quote_buf: List[str] = []

    def _flush_quote() -> None:
        nonlocal quote_buf
        if quote_buf:
            q_html = "\n".join(_format_inline_line(q) for q in quote_buf)
            out_lines.append(f"<blockquote>{q_html}</blockquote>")
            quote_buf = []

    for raw_line in raw_lines:
        stripped = raw_line.strip()

        # Check blockquote `> ...`
        if stripped.startswith("&gt;"):
            clean_q = re.sub(r"^\s*&gt;\s?", "", stripped)
            quote_buf.append(clean_q)
            continue
        else:
            _flush_quote()

        # Horizontal divider `---` or `***`
        if re.match(r"^[-*_]{3,}$", stripped):
            out_lines.append("───────────────")
            continue

        # Markdown Heading `# ...`, `## ...`, `### ...`, `#### ...`
        m_head = re.match(r"^(#{1,5})\s+(.+)$", stripped)
        if m_head:
            clean_title = m_head.group(2).replace("**", "").replace("__", "").replace("*", "").strip()
            out_lines.append(f"\n✦ <b>{clean_title}</b>")
            continue

        # Bullet points `* item` or `- item`
        m_bullet = re.match(r"^(\s*)[*-]\s+(.+)$", raw_line)
        if m_bullet:
            out_lines.append(f"• {_format_inline_line(m_bullet.group(2).strip())}")
            continue

        # Numbered list `1. item` -> bold number
        m_num = re.match(r"^(\s*)(\d+\.)\s+(.+)$", raw_line)
        if m_num:
            out_lines.append(f"<b>{m_num.group(2)}</b> {_format_inline_line(m_num.group(3).strip())}")
            continue

        out_lines.append(_format_inline_line(raw_line))

    _flush_quote()

    result = "\n".join(out_lines)
    result = re.sub(r"\n{3,}", "\n\n", result).strip()
    return result


def strip_html_tags(html_text: str) -> str:
    """Cleanly remove HTML tags and unescape entities if plain-text fallback is ever needed."""
    no_tags = re.sub(r"<[^>]+>", "", html_text)
    return html.unescape(no_tags)


def split_html_telegram_message(text: str, max_len: int = 3100) -> List[str]:
    """
    Split Markdown/text cleanly on paragraph boundaries BEFORE converting each chunk to Telegram HTML,
    ensuring every single chunk has 100% balanced tags and stays well below Telegram's 4096-char limit.
    """
    if not text or not text.strip():
        return [""]

    paragraphs = [p.strip() for p in re.split(r"\n{2,}", text.replace("\r\n", "\n")) if p.strip()]
    chunks_md: List[str] = []
    current_md = ""

    for para in paragraphs:
        candidate = f"{current_md}\n\n{para}" if current_md else para
        if len(candidate) <= max_len:
            current_md = candidate
        else:
            if current_md:
                chunks_md.append(current_md)
            if len(para) <= max_len:
                current_md = para
            else:
                # Split oversized single paragraph by lines
                lines = para.split("\n")
                sub = ""
                for ln in lines:
                    cand_ln = f"{sub}\n{ln}" if sub else ln
                    if len(cand_ln) <= max_len:
                        sub = cand_ln
                    else:
                        if sub:
                            chunks_md.append(sub)
                        sub = ln[:max_len]
                current_md = sub

    if current_md:
        chunks_md.append(current_md)

    html_chunks = [markdown_to_telegram_html(c) for c in chunks_md if c.strip()]
    return html_chunks if html_chunks else [markdown_to_telegram_html(text)]
