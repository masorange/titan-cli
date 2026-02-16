"""
Jira Formatting Utilities

Shared formatting functions for Jira data.
Used by mappers to convert raw API data into UI-friendly strings.

All functions are pure - no side effects, easily testable.
"""

from datetime import datetime
from typing import Optional


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
        priority: Priority name ("Highest", "High", "Medium", "Low", "Lowest")

    Returns:
        Icon string

    Examples:
        >>> get_priority_icon("Highest")
        '🔴'
        >>> get_priority_icon("High")
        '🟠'
        >>> get_priority_icon("Medium")
        '🟡'
        >>> get_priority_icon("Low")
        '🟢'
        >>> get_priority_icon("Lowest")
        '🔵'
        >>> get_priority_icon("Unknown")
        '⚪'
    """
    icons = {
        "highest": "🔴",
        "high": "🟠",
        "medium": "🟡",
        "low": "🟢",
        "lowest": "🔵",
    }
    return icons.get(priority.lower(), "⚪")


def extract_text_from_adf(adf: any) -> str:
    """
    Extract plain text from Atlassian Document Format (ADF).

    Recursively traverses the ADF tree and extracts all text nodes.

    Args:
        adf: ADF structure (dict) or plain string

    Returns:
        Plain text string

    Examples:
        >>> adf = {
        ...     "type": "doc",
        ...     "content": [{
        ...         "type": "paragraph",
        ...         "content": [{"type": "text", "text": "Hello"}]
        ...     }]
        ... }
        >>> extract_text_from_adf(adf)
        'Hello'
        >>> extract_text_from_adf("Plain string")
        'Plain string'
        >>> extract_text_from_adf(None)
        ''
    """
    # Handle plain string (old API format)
    if isinstance(adf, str):
        return adf

    # Handle None
    if not adf:
        return ""

    # Handle ADF structure
    if not isinstance(adf, dict):
        return ""

    text_parts = []

    def extract_recursive(node):
        if isinstance(node, dict):
            # Text node
            if node.get("type") == "text":
                text_parts.append(node.get("text", ""))

            # Recurse into content
            if "content" in node:
                for child in node["content"]:
                    extract_recursive(child)

    extract_recursive(adf)
    return " ".join(text_parts)


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
