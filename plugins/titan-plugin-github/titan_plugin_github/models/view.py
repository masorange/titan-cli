"""
GitHub UI/View Models

View models optimized for rendering GitHub data in Textual TUI widgets.
Decoupled from network/API models to keep widgets stable when API changes.

These models are GitHub-specific and live in the GitHub plugin, not in the core.
"""

from dataclasses import dataclass
from typing import Any, List, Optional
from datetime import datetime


def _format_date(iso_date: str) -> str:
    """
    Format ISO 8601 date to DD/MM/YYYY HH:MM:SS.

    Args:
        iso_date: ISO 8601 formatted date string

    Returns:
        Formatted date string, or original if parsing fails
    """
    try:
        date_obj = datetime.fromisoformat(str(iso_date).replace('Z', '+00:00'))
        return date_obj.strftime("%d/%m/%Y %H:%M:%S")
    except Exception:
        return iso_date


@dataclass
class UIComment:
    """
    UI model for displaying a single comment.

    Optimized for rendering - contains only what widgets need, with pre-formatted data.
    """
    id: int
    body: str
    author_name: str
    formatted_date: str  # Pre-formatted as "DD/MM/YYYY HH:MM:SS"
    path: Optional[str] = None
    line: Optional[int] = None
    diff_hunk: Optional[str] = None

    @classmethod
    def from_review_comment(cls, comment: 'Any', is_outdated: bool = False) -> 'UIComment':
        """
        Convert a PRReviewComment (network model) to UIComment (view model).

        Args:
            comment: PRReviewComment instance from GraphQL
            is_outdated: Whether this comment is on outdated code

        Returns:
            UIComment instance optimized for rendering
        """
        # Extract author name
        author_name = comment.author.login if comment.author else "Unknown"

        # For outdated comments, use originalLine because diffHunk reflects old state
        # For current comments, use line
        if is_outdated and comment.original_line:
            line_number = comment.original_line
        else:
            line_number = comment.line or comment.original_line

        return cls(
            id=comment.id,
            body=comment.body,
            author_name=author_name,
            formatted_date=_format_date(comment.created_at),
            path=comment.path,
            line=line_number,  # originalLine for outdated, line otherwise
            diff_hunk=comment.diff_hunk
        )

    @classmethod
    def from_issue_comment(cls, comment: 'Any') -> 'UIComment':
        """
        Convert a PRIssueComment (network model) to UIComment (view model).

        Args:
            comment: PRIssueComment instance from GraphQL

        Returns:
            UIComment instance optimized for rendering
        """
        # Extract author name
        author_name = comment.author.login if comment.author else "Unknown"

        return cls(
            id=comment.id,
            body=comment.body,
            author_name=author_name,
            formatted_date=_format_date(comment.created_at),
            path=None,
            line=None,
            diff_hunk=None
        )


@dataclass
class UICommentThread:
    """
    UI model for displaying a comment thread.

    Contains a main comment, its replies, and thread metadata.
    Optimized for rendering in the TUI.
    """
    thread_id: str  # GraphQL node ID (for resolving/actions)
    main_comment: UIComment
    replies: List[UIComment]
    is_resolved: bool
    is_outdated: bool

    @classmethod
    def from_review_thread(cls, thread: 'Any') -> 'UICommentThread':
        """
        Convert a PRReviewThread (network model) to UICommentThread (view model).

        Args:
            thread: PRReviewThread instance from GraphQL

        Returns:
            UICommentThread instance optimized for rendering
        """
        # Convert main comment with outdated status
        main_comment = None
        if thread.main_comment:
            main_comment = UIComment.from_review_comment(
                thread.main_comment,
                is_outdated=thread.is_outdated
            )

        # Convert replies with outdated status
        replies = [
            UIComment.from_review_comment(reply, is_outdated=thread.is_outdated)
            for reply in thread.replies
        ]

        return cls(
            thread_id=thread.id,
            main_comment=main_comment,
            replies=replies,
            is_resolved=thread.is_resolved,
            is_outdated=thread.is_outdated
        )


__all__ = ["UIComment", "UICommentThread"]
