"""Network model for Git worktree - faithful to git CLI output."""
from dataclasses import dataclass
from typing import Optional


@dataclass
class NetworkGitWorktree:
    """
    Network model for git worktree - raw data from git CLI.

    Represents a git worktree as returned by git worktree list command.
    No formatting or UI-specific data.
    """
    path: str
    branch: Optional[str] = None
    commit: Optional[str] = None
    is_bare: bool = False
    is_detached: bool = False
