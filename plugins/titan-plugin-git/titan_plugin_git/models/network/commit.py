"""Network model for Git commit - faithful to git CLI output."""
from dataclasses import dataclass, field
from typing import List


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
    parents: List[str] = field(default_factory=list)  # %P, oldest-first as git prints it
    refs: List[str] = field(default_factory=list)  # %D, e.g. ["HEAD -> main", "origin/main"]
