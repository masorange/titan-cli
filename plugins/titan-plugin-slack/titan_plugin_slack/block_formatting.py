"""Slack Block Kit formatting toolkit.

`SlackFormatter` (in `formatting.py`) renders Markdown as a single mrkdwn
string. `SlackBlockFormatter` renders the same kind of Markdown source as a
list of Block Kit blocks instead - one `header`/`section`/`divider` block per
structural element - so a message can use Slack's richer message layout
without a caller having to learn Block Kit's JSON shape by hand.

`to_blocks` is the "just give it Markdown" entry point, mirroring
`SlackFormatter.to_mrkdwn`. The `section`/`header`/`divider`/`context`/
`fields` builders are exposed separately for callers that want to assemble a
message explicitly (e.g. mixing generated blocks with a hand-built one).

Slack always uses the message's `text` field as a fallback for notifications
and surfaces that don't render blocks, so callers posting `blocks` should
still pass a plain-text/mrkdwn `text` alongside them - typically
`SlackFormatter.to_mrkdwn` of the same source.
"""

import re
from typing import Any, Dict, List

from .formatting import (
    BULLET_RE,
    HEADER_RE,
    HR_RE,
    convert_inline,
    find_table_block_end,
    render_table,
    split_on_code_fences,
    split_table_row,
    strip_markdown_emphasis,
)

SECTION_TEXT_LIMIT = 3000
HEADER_TEXT_LIMIT = 150
MAX_HEADER_LEVEL = 2


class SlackBlockFormatter:
    """Namespace of stateless helpers that build Slack Block Kit blocks."""

    @staticmethod
    def to_blocks(text: str) -> List[Dict[str, Any]]:
        """
        Convert a standard Markdown document into Slack Block Kit blocks.

        Recognizes the same structure as `SlackFormatter.to_mrkdwn` - headers,
        bullet lists, pipe tables, horizontal rules, and fenced code blocks -
        but renders each as its own block (`header`, `divider`, `section`)
        instead of one long mrkdwn string. Consecutive plain lines and
        consecutive bullet lines are grouped into a single `section` block;
        oversized sections are split to stay under Slack's per-block text
        limit.

        Args:
            text: Standard Markdown source text.

        Returns:
            A list of Block Kit block dicts, ready to pass as `blocks` to
            `chat.postMessage`.
        """
        blocks: List[Dict[str, Any]] = []
        for segment, is_code in split_on_code_fences(text):
            if is_code:
                blocks.extend(SlackBlockFormatter._flush_paragraph([segment]))
            else:
                blocks.extend(SlackBlockFormatter._prose_segment_to_blocks(segment))
        return blocks

    @staticmethod
    def section(text: str) -> Dict[str, Any]:
        """Build a `section` block from already Slack-ready mrkdwn text."""
        return {"type": "section", "text": {"type": "mrkdwn", "text": text}}

    @staticmethod
    def header(text: str) -> Dict[str, Any]:
        """Build a `header` block. `text` must be plain text (no mrkdwn, max 150 chars)."""
        return {"type": "header", "text": {"type": "plain_text", "text": text}}

    @staticmethod
    def divider() -> Dict[str, Any]:
        """Build a `divider` block."""
        return {"type": "divider"}

    @staticmethod
    def context(text: str) -> Dict[str, Any]:
        """Build a `context` block from already Slack-ready mrkdwn text."""
        return {"type": "context", "elements": [{"type": "mrkdwn", "text": text}]}

    @staticmethod
    def fields(texts: List[str]) -> Dict[str, Any]:
        """Build a `section` block with up to 10 side-by-side mrkdwn fields."""
        return {
            "type": "section",
            "fields": [{"type": "mrkdwn", "text": text} for text in texts[:10]],
        }

    @staticmethod
    def _prose_segment_to_blocks(text: str) -> List[Dict[str, Any]]:
        """Convert a non-code-fence block into header/divider/section blocks."""
        lines = text.split("\n")
        blocks: List[Dict[str, Any]] = []
        buffer: List[str] = []
        i = 0
        while i < len(lines):
            table_end = find_table_block_end(lines, i)
            if table_end is not None:
                blocks.extend(SlackBlockFormatter._flush_paragraph(buffer))
                buffer = []
                header, *rows = [
                    split_table_row(line) for line in (lines[i], *lines[i + 2 : table_end])
                ]
                blocks.extend(
                    SlackBlockFormatter._flush_paragraph([render_table(rows, headers=header)])
                )
                i = table_end
                continue

            line = lines[i]

            if HR_RE.match(line):
                blocks.extend(SlackBlockFormatter._flush_paragraph(buffer))
                buffer = []
                blocks.append(SlackBlockFormatter.divider())
                i += 1
                continue

            header_match = HEADER_RE.match(line)
            if header_match:
                blocks.extend(SlackBlockFormatter._flush_paragraph(buffer))
                buffer = []
                blocks.append(SlackBlockFormatter._header_block(header_match))
                i += 1
                continue

            if not line.strip():
                blocks.extend(SlackBlockFormatter._flush_paragraph(buffer))
                buffer = []
                i += 1
                continue

            bullet_match = BULLET_RE.match(line)
            if bullet_match:
                indent, rest = bullet_match.groups()
                buffer.append(f"{indent}• {convert_inline(rest)}")
            else:
                buffer.append(convert_inline(line))
            i += 1

        blocks.extend(SlackBlockFormatter._flush_paragraph(buffer))
        return blocks

    @staticmethod
    def _header_block(header_match: "re.Match[str]") -> Dict[str, Any]:
        """Build a `header` block for a Markdown heading, falling back to a bold section."""
        level = len(header_match.group(1))
        plain_title = strip_markdown_emphasis(header_match.group(2).strip())
        if level <= MAX_HEADER_LEVEL and 0 < len(plain_title) <= HEADER_TEXT_LIMIT:
            return SlackBlockFormatter.header(plain_title)
        return SlackBlockFormatter.section(f"*{convert_inline(header_match.group(2).strip())}*")

    @staticmethod
    def _flush_paragraph(lines: List[str]) -> List[Dict[str, Any]]:
        """Join buffered lines into one or more `section` blocks, chunked to the text limit."""
        text = "\n".join(lines).strip("\n")
        if not text:
            return []
        return [SlackBlockFormatter.section(chunk) for chunk in SlackBlockFormatter._chunk_text(text)]

    @staticmethod
    def _chunk_text(text: str, limit: int = SECTION_TEXT_LIMIT) -> List[str]:
        """Split text into chunks at line boundaries, each at most `limit` chars."""
        if len(text) <= limit:
            return [text]

        chunks: List[str] = []
        current = ""
        for line in text.split("\n"):
            candidate = f"{current}\n{line}" if current else line
            if len(candidate) <= limit:
                current = candidate
                continue
            if current:
                chunks.append(current)
                current = ""
            while len(line) > limit:
                chunks.append(line[:limit])
                line = line[limit:]
            current = line
        if current:
            chunks.append(current)
        return chunks


__all__ = ["SlackBlockFormatter"]
