"""Network model for Git commit - faithful to git CLI output."""
from dataclasses import dataclass


@dataclass
class NetworkGitCommit:
    """
    Network model for git commit - raw data from git CLI.

    Represents a git commit as returned by git log commands.
    No formatting or UI-specific data.
    """
    hash: str
    message: str
    author: str
    date: str  # Raw git date string
