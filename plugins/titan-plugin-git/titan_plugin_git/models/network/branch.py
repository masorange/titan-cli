"""Network model for Git branch - faithful to git CLI output."""
from dataclasses import dataclass
from typing import Optional


@dataclass
class NetworkGitBranch:
    """
    Network model for git branch - raw data from git CLI.

    Represents a git branch as returned by git CLI commands.
    No formatting or UI-specific data.
    """
    name: str
    is_current: bool = False
    is_remote: bool = False
    upstream: Optional[str] = None
