"""Network model for Git status - faithful to git CLI output."""
from dataclasses import dataclass
from typing import List


@dataclass
class NetworkGitStatus:
    """
    Network model for git status - raw data from git CLI.

    Represents repository status as returned by git status command.
    No formatting or UI-specific data.
    """
    branch: str
    is_clean: bool
    modified_files: List[str]
    untracked_files: List[str]
    staged_files: List[str]
    ahead: int = 0
    behind: int = 0
