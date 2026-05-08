"""Formatting utilities for UI display."""

from datetime import datetime


def format_iso_date(iso_date: str) -> str:
    """Convert ISO 8601 date string to readable format.

    Args:
        iso_date: ISO 8601 date string

    Returns:
        Formatted date string (DD/MM/YYYY HH:MM:SS) or "N/A" if invalid
    """
    if not iso_date:
        return "N/A"

    try:
        dt = datetime.fromisoformat(iso_date.replace("Z", "+00:00"))
        return dt.strftime("%d/%m/%Y %H:%M:%S")
    except (ValueError, AttributeError):
        return "N/A"


def get_completeness_icon(percentage: float) -> str:
    """Get icon based on translation completeness percentage.

    Args:
        percentage: Completeness percentage (0-100)

    Returns:
        Icon representing completeness level
    """
    if percentage >= 100:
        return "🟢"
    elif percentage >= 75:
        return "🟡"
    elif percentage >= 25:
        return "🟠"
    else:
        return "🔴"


def format_description(description: str | None) -> str:
    """Format project description for display.

    Args:
        description: Project description or None

    Returns:
        Formatted description or "No description"
    """
    if not description or description.strip() == "":
        return "No description"
    return description.strip()


def truncate_text(text: str, max_length: int = 50) -> str:
    """Truncate text to maximum length with ellipsis.

    Args:
        text: Text to truncate
        max_length: Maximum length before truncation

    Returns:
        Truncated text with ... if needed
    """
    if len(text) <= max_length:
        return text
    return text[: max_length - 3] + "..."
