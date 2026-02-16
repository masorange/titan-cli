"""Network model for Git tag - faithful to git CLI output."""
from dataclasses import dataclass
from typing import Optional


@dataclass
class NetworkGitTag:
    """
    Network model for git tag - raw data from git CLI.

    Represents a git tag as returned by git tag commands.
    No formatting or UI-specific data.
    """
    name: str
    commit_hash: Optional[str] = None
    message: Optional[str] = None
