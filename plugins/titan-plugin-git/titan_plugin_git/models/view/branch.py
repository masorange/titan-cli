"""UI model for Git branch - pre-formatted for display."""
from dataclasses import dataclass
from typing import Optional


@dataclass
class UIGitBranch:
    """
    UI model for git branch - formatted for display.

    Contains pre-formatted data with icons and indicators.
    """
    name: str
    display_name: str  # With current marker: "* main" or "  feature"
    is_current: bool
    is_remote: bool
    upstream: Optional[str] = None
    upstream_info: str = ""  # e.g., "→ origin/main"
    last_commit_date: Optional[str] = None  # ISO 8601 of the branch's last commit
    formatted_date: str = ""  # Human-readable: "today", "3 d", "2 w"
