"""
Jira Formatting Utilities

Shared formatting functions for Jira data.
Used by mappers to convert raw API data into UI-friendly strings.

All functions are pure - no side effects, easily testable.
"""

from datetime import datetime
from typing import Any, List, Optional


def format_jira_date(iso_date: Optional[str]) -> str:
    """
    Format Jira ISO 8601 date to DD/MM/YYYY HH:MM:SS.

    Args:
        iso_date: ISO 8601 date string (e.g., "2025-01-15T10:30:45.000+0000")

    Returns:
        Formatted date string or "Unknown" if None/invalid

    Examples:
        >>> format_jira_date("2025-01-15T10:30:45.000+0000")
        '15/01/2025 10:30:45'
        >>> format_jira_date("2025-01-15T10:30:45Z")
        '15/01/2025 10:30:45'
        >>> format_jira_date(None)
        'Unknown'
        >>> format_jira_date("")
        'Unknown'
    """
    if not iso_date:
        return "Unknown"

    try:
        # Handle different ISO formats (with/without milliseconds, with Z or offset)
        # Remove milliseconds if present
        if "." in iso_date:
            iso_date = iso_date.split(".")[0]
        # Remove Z if present
        iso_date = iso_date.replace("Z", "")
        # Parse and format
        dt = datetime.fromisoformat(iso_date)
        return dt.strftime("%d/%m/%Y %H:%M:%S")
    except (ValueError, AttributeError):
        return "Unknown"


def get_status_icon(status_category: str) -> str:
    """
    Get icon for Jira status category.

    Args:
        status_category: Status category key ("new", "indeterminate", "done")

    Returns:
        Icon string

    Examples:
        >>> get_status_icon("new")
        '🟡'
        >>> get_status_icon("indeterminate")
        '🔵'
        >>> get_status_icon("done")
        '🟢'
        >>> get_status_icon("unknown")
        '⚪'
    """
    icons = {
        "new": "🟡",           # To Do
        "indeterminate": "🔵", # In Progress
        "done": "🟢",          # Done
    }
    return icons.get(status_category.lower(), "⚪")


def get_issue_type_icon(issue_type: str) -> str:
    """
    Get icon for Jira issue type.

    Args:
        issue_type: Issue type name ("Bug", "Story", "Task", etc.)

    Returns:
        Icon string

    Examples:
        >>> get_issue_type_icon("Bug")
        '🐛'
        >>> get_issue_type_icon("Story")
        '📖'
        >>> get_issue_type_icon("Task")
        '✅'
        >>> get_issue_type_icon("Epic")
        '🎯'
        >>> get_issue_type_icon("Sub-task")
        '📝'
        >>> get_issue_type_icon("Unknown")
        '📋'
    """
    icons = {
        "bug": "🐛",
        "story": "📖",
        "task": "✅",
        "epic": "🎯",
        "sub-task": "📝",
        "subtask": "📝",
        "improvement": "🔧",
        "new feature": "✨",
    }
    return icons.get(issue_type.lower(), "📋")


def get_priority_icon(priority: str) -> str:
    """
    Get icon for Jira priority.

    Args:
        priority: Priority name (case-insensitive). Supports standard Jira priorities:
                 Highest, High, Medium, Low, Lowest. Returns a default icon for unknown values.

    Returns:
        Icon string representing the priority level
    """
    icons = {
        "highest": "🔴",
        "high": "🟠",
        "medium": "🟡",
        "low": "🟢",
        "lowest": "🔵",
    }
    return icons.get(priority.lower(), "⚪")


def extract_text_from_adf(adf: Any) -> str:
    """
    Plain text from Atlassian Document Format (ADF), keeping its layout.

    Blocks (paragraphs, headings, lists, code, quotes, tables) become lines
    separated by a blank line; list items get "•" or their number, nested ones
    indented; code is indented. Inline nodes that carry no text node of their
    own still read: a link card as its URL, a mention as "@name", an emoji,
    a date, a status lozenge. A plain string (the old API format) is returned
    as it is; anything else yields "".
    """
    if isinstance(adf, str):
        return adf
    if not isinstance(adf, dict) or not adf:
        return ""
    return "\n".join(_adf_blocks(adf.get("content", []) if adf.get("type") == "doc" else [adf])).strip("\n")


def _adf_inline(nodes: list) -> str:
    out = []
    for node in nodes or []:
        kind = node.get("type")
        attrs = node.get("attrs", {}) or {}
        if kind == "text":
            text = node.get("text", "")
            href = next((m.get("attrs", {}).get("href") for m in node.get("marks", []) if m.get("type") == "link"), None)
            out.append(f"{text} ({href})" if href and href != text else text)
        elif kind == "hardBreak":
            out.append("\n")
        elif kind == "mention":
            name = attrs.get("text") or "someone"
            out.append(name if name.startswith("@") else f"@{name}")
        elif kind == "emoji":
            out.append(attrs.get("text") or attrs.get("shortName", ""))
        elif kind in ("inlineCard", "blockCard", "embedCard"):
            out.append(attrs.get("url", ""))
        elif kind == "date":
            out.append(format_jira_date(attrs.get("timestamp")) if attrs.get("timestamp") else "")
        elif kind == "status":
            out.append(f"[{attrs.get('text', '')}]")
        elif "content" in node:
            out.append(_adf_inline(node["content"]))
    return "".join(out)


def _adf_blocks(nodes: list, indent: str = "") -> List[str]:
    """Lines for a list of block nodes, a blank line between blocks."""
    lines: List[str] = []

    def add(block: List[str]) -> None:
        if not block:
            return
        if lines and lines[-1] != "":
            lines.append("")
        lines.extend(block)

    for node in nodes or []:
        kind = node.get("type")
        content = node.get("content", [])
        if kind in ("paragraph", "heading"):
            text = _adf_inline(content)
            add([indent + line for line in text.split("\n")] if text.strip() else [])
        elif kind in ("bulletList", "orderedList"):
            start = (node.get("attrs", {}) or {}).get("order", 1)
            items: List[str] = []
            for n, item in enumerate(content):
                marker = "•" if kind == "bulletList" else f"{start + n}."
                body = [ln for ln in _adf_blocks(item.get("content", []), indent + " " * (len(marker) + 1)) if ln != ""]
                if body:
                    first = body[0][len(indent) + len(marker) + 1:]
                    items.append(f"{indent}{marker} {first}")
                    items.extend(body[1:])
            add(items)
        elif kind == "codeBlock":
            code = "".join(t.get("text", "") for t in content)
            add([f"{indent}    {line}" for line in code.split("\n")])
        elif kind == "blockquote":
            add([f"{indent}> {line[len(indent):]}" if line else line for line in _adf_blocks(content, indent)])
        elif kind == "rule":
            add([indent + "───"])
        elif kind == "table":
            rows = []
            for row in content:
                cells = [" ".join(ln.strip() for ln in _adf_blocks(cell.get("content", [])) if ln.strip())
                         for cell in row.get("content", [])]
                rows.append(indent + " | ".join(cells))
            add(rows)
        elif kind in ("mediaSingle", "mediaGroup", "media"):
            add([indent + "[attachment]"])
        elif kind == "expand":
            title = (node.get("attrs", {}) or {}).get("title")
            add(([indent + title] if title else []) + _adf_blocks(content, indent))
        elif kind in ("inlineCard", "blockCard", "embedCard", "mention", "emoji", "text"):
            add([indent + _adf_inline([node])])
        elif content:
            add(_adf_blocks(content, indent))
    return lines


def truncate_text(text: Optional[str], max_length: int = 60) -> str:
    """
    Truncate text to maximum length.

    Args:
        text: Text to truncate
        max_length: Maximum length

    Returns:
        Truncated text or "N/A" if None

    Examples:
        >>> truncate_text("Short")
        'Short'
        >>> truncate_text("A" * 100, max_length=10)
        'AAAAAAAAAA'
        >>> truncate_text(None)
        'N/A'
        >>> truncate_text("")
        'N/A'
    """
    if not text or not text.strip():
        return "N/A"

    return text[:max_length]


__all__ = [
    "format_jira_date",
    "get_status_icon",
    "get_issue_type_icon",
    "get_priority_icon",
    "extract_text_from_adf",
    "truncate_text",
]
