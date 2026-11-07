"""
Telegram Rich HTML Formatter for MATRIX ("Матрица") Numerology Bot.
"""
from __future__ import annotations

import html
import re
from typing import List


def markdown_to_telegram_html(text: str) -> str:
    if not text:
        return ""

    escaped = html.escape(text)
    code_Blocks: List[str] = []

    def _save_code(match: re.Match) -> str:
        code_Blocks.append(f"<code>{match.group(1)}</code>")
        return f"@@CODEBLOCK_{len(code_Blocks) - 1}@@"

    escaped = re.sub(r"`([^`\n]+)`", _save_code, escaped)
    escaped = re.sub(r"^\s*[-*_]{3,}\s*$", "━━━━━━━━━━━━━━━", escaped, flags=re.M)

    def _format_heading(match: re.Match) -> str:
        title = match.group(2).strip().replace("**", "")
        return f"\n🔢 <b>{title.upper()}</b>"

    escaped = re.sub(r"^(#{1,4})\s+(.+)$", _format_heading, escaped, flags=re.M)

    lines = escaped.split("\n")
    out_lines: List[str] = []
    in_quote = False
    quote_buf: List[str] = []

    for line in lines:
        if line.lstrip().startswith("&gt;"):
            clean_q = re.sub(r"^\s*&gt;\s?", "", line)
            quote_buf.append(clean_q)
            in_quote = True
        else:
            if in_quote:
                out_lines.append("<blockquote>" + "\n".join(quote_buf) + "</blockquote>")
                quote_buf = []
                in_quote = False
            line = re.sub(r"^(\s*)[*-]\s+", r"\1• ", line)
            out_lines.append(line)

    if in_quote and quote_buf:
        out_lines.append("<blockquote>" + "\n".join(quote_buf) + "</blockquote>")

    escaped = "\n".join(out_lines)
    escaped = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", escaped, flags=re.S)
    escaped = re.sub(r"__(.+?)__", r"<b>\1</b>", escaped, flags=re.S)
    escaped = re.sub(r"(?<!\w)\*([^\*\n]+?)\*(?!\w)", r"<i>\1</i>", escaped)

    for idx, cb in enumerate(code_Blocks):
        escaped = escaped.replace(f"@@CODEBLOCK_{idx}@@", cb)

    escaped = re.sub(r"\n{3,}", "\n\n", escaped).strip()
    return escaped


def split_html_telegram_message(text: str, max_len: int = 3800) -> List[str]:
    paragraphs = text.split("\n\n")
    chunks: List[str] = []
    current_md = ""

    for para in paragraphs:
        candidate = f"{current_md}\n\n{para}".strip() if current_md else para
        if len(candidate) <= max_len:
            current_md = candidate
        else:
            if current_md:
                chunks.append(markdown_to_telegram_html(current_md))
            if len(para) <= max_len:
                current_md = para
            else:
                for i in range(0, len(para), max_len):
                    chunks.append(markdown_to_telegram_html(para[i : i + max_len]))
                current_md = ""

    if current_md:
        chunks.append(markdown_to_telegram_html(current_md))

    return chunks if chunks else [markdown_to_telegram_html(text)]
