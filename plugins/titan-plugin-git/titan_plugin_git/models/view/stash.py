"""UI model for a Git stash - pre-formatted for display."""
from dataclasses import dataclass


@dataclass
class UIGitStash:
    """A stash as the screens show it: where it came from and what it was called."""

    ref: str
    branch: str
    message: str
    formatted_date: str = ""
    hash: str = ""  # names the stash like a commit, whatever place it holds in the list
