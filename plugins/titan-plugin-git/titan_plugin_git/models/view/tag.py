"""UI model for Git tag - pre-formatted for display."""
from dataclasses import dataclass
from typing import Optional


@dataclass
class UIGitTag:
    """
    UI model for git tag - formatted for display.

    Contains pre-formatted data with icons and short hashes.
    """
    name: str
    display_name: str  # With icon: "🏷  v1.0.0"
    commit_hash: Optional[str] = None
    commit_hash_short: Optional[str] = None  # First 7 characters
    message: Optional[str] = None
    message_summary: Optional[str] = None  # First line only
