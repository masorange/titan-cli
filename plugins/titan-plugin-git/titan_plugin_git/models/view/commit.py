"""UI model for Git commit - pre-formatted for display."""
from dataclasses import dataclass


@dataclass
class UIGitCommit:
    """
    UI model for git commit - formatted for display.

    Contains pre-formatted data with icons and short hashes.
    """
    hash: str
    short_hash: str  # First 7 characters
    message: str
    message_subject: str  # First line of commit message
    author: str
    author_short: str  # Just name, no email
    date: str  # Raw date
    formatted_date: str  # Human-readable: "2 days ago" or "2026-01-15"
