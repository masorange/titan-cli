# plugins/titan-plugin-github/titan_plugin_github/models/formatting.py
"""
Formatting Utilities

Shared formatting functions for converting network data to UI-friendly strings.
All presentation/display logic should use these utilities for consistency.
"""
from datetime import datetime
from typing import Optional


def format_date(iso_date: str) -> str:
    """
    Format ISO 8601 date to DD/MM/YYYY HH:MM:SS.

    Used across all view models for consistent date formatting.

    Args:
        iso_date: ISO 8601 formatted date string (e.g., "2024-01-15T10:30:00Z")

    Returns:
        Formatted date string "DD/MM/YYYY HH:MM:SS", or original if parsing fails

    Examples:
        >>> format_date("2024-01-15T10:30:00Z")
        '15/01/2024 10:30:00'
        >>> format_date("invalid")
        'invalid'
    """
    try:
        date_obj = datetime.fromisoformat(str(iso_date).replace('Z', '+00:00'))
        return date_obj.strftime("%d/%m/%Y %H:%M:%S")
    except Exception:
        return iso_date


def get_pr_status_icon(state: str, is_draft: bool) -> str:
    """
    Get emoji icon for PR state.

    Args:
        state: PR state (OPEN, CLOSED, MERGED)
        is_draft: Whether PR is draft

    Returns:
        Emoji string

    Examples:
        >>> get_pr_status_icon("MERGED", False)
        '🟣'
        >>> get_pr_status_icon("OPEN", True)
        '📝'
    """
    if state == "MERGED":
        return "🟣"
    elif state == "CLOSED":
        return "🔴"
    elif is_draft:
        return "📝"
    elif state == "OPEN":
        return "🟢"
    return "⚪"


def get_issue_status_icon(state: str) -> str:
    """
    Get emoji icon for issue state.

    Args:
        state: Issue state (OPEN, CLOSED)

    Returns:
        Emoji string

    Examples:
        >>> get_issue_status_icon("OPEN")
        '🟢'
        >>> get_issue_status_icon("CLOSED")
        '🔴'
    """
    if state == "OPEN":
        return "🟢"
    elif state == "CLOSED":
        return "🔴"
    return "⚪"


def format_pr_stats(additions: int, deletions: int) -> str:
    """
    Format PR additions/deletions as "+X -Y".

    Args:
        additions: Number of lines added
        deletions: Number of lines deleted

    Returns:
        Formatted string

    Examples:
        >>> format_pr_stats(123, 45)
        '+123 -45'
    """
    return f"+{additions} -{deletions}"


def format_branch_info(head_ref: str, base_ref: str) -> str:
    """
    Format branch info as "head → base".

    Args:
        head_ref: Head branch name
        base_ref: Base branch name

    Returns:
        Formatted string

    Examples:
        >>> format_branch_info("feat/xyz", "develop")
        'feat/xyz → develop'
    """
    return f"{head_ref} → {base_ref}"


def calculate_review_summary(reviews: list) -> str:
    """
    Calculate review status summary from list of reviews.

    Args:
        reviews: List of review objects with 'state' attribute

    Returns:
        Formatted review summary string

    Examples:
        >>> reviews = [Mock(state="APPROVED"), Mock(state="APPROVED")]
        >>> calculate_review_summary(reviews)
        '✅ 2 approved'
    """
    if not reviews:
        return "No reviews"

    approved = sum(1 for r in reviews if r.state == "APPROVED")
    changes = sum(1 for r in reviews if r.state == "CHANGES_REQUESTED")

    if approved > 0 and changes == 0:
        return f"✅ {approved} approved"
    elif changes > 0:
        return f"❌ {changes} changes requested"
    else:
        return f"💬 {len(reviews)} comments"


def get_review_state_icon(state: str) -> str:
    """
    Get icon for review state.

    Args:
        state: Review state (APPROVED, CHANGES_REQUESTED, COMMENTED, PENDING)

    Returns:
        Icon representing the review state

    Examples:
        >>> get_review_state_icon("APPROVED")
        '🟢'
        >>> get_review_state_icon("CHANGES_REQUESTED")
        '🔴'
    """
    icons = {
        "APPROVED": "🟢",
        "CHANGES_REQUESTED": "🔴",
        "COMMENTED": "💬",
        "PENDING": "⏳",
    }
    return icons.get(state.upper(), "⚪")


def format_short_sha(sha: Optional[str], length: int = 7) -> str:
    """
    Format commit SHA to short format.

    Args:
        sha: Full commit SHA (40 characters)
        length: Number of characters to show (default: 7)

    Returns:
        Short SHA or empty string if None

    Examples:
        >>> format_short_sha("abc123def456")
        'abc123d'
        >>> format_short_sha(None)
        ''
    """
    if not sha:
        return ""
    return sha[:length]


__all__ = [
    "format_date",
    "get_pr_status_icon",
    "get_issue_status_icon",
    "format_pr_stats",
    "format_branch_info",
    "calculate_review_summary",
    "get_review_state_icon",
    "format_short_sha",
]
