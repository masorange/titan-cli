"""UI model for Git status - pre-formatted for display."""
from dataclasses import dataclass
from typing import List


@dataclass
class UIGitStatus:
    """
    UI model for git status - formatted for display.

    Contains pre-formatted data with icons and indicators.
    """
    branch: str
    is_clean: bool
    modified_files: List[str]
    untracked_files: List[str]
    staged_files: List[str]
    ahead: int = 0
    behind: int = 0
    clean_icon: str = ""  # "✓" if clean, "✗" if dirty
    status_summary: str = ""  # e.g., "Clean" or "3 modified, 2 untracked"
    sync_status: str = ""  # e.g., "↑2 ↓1" or "↑3" or "synced"
