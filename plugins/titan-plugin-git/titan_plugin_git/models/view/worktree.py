"""UI model for Git worktree - pre-formatted for display."""
from dataclasses import dataclass
from typing import Optional


@dataclass
class UIGitWorktree:
    """
    UI model for git worktree - formatted for display.

    Contains pre-formatted data with icons and status indicators.
    """
    path: str
    path_short: str  # Relative or abbreviated path
    branch: Optional[str] = None
    branch_display: str = ""  # "main" or "(detached)" or "(bare)"
    commit: Optional[str] = None
    commit_short: Optional[str] = None  # First 7 characters
    is_bare: bool = False
    is_detached: bool = False
    status_icon: str = ""  # "📂" for regular, "🔓" for detached, "📦" for bare
