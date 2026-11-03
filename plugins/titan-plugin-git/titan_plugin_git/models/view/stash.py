"""UI model for a Git stash - pre-formatted for display."""
from dataclasses import dataclass


@dataclass
class UIGitStash:
    """A stash as the screens show it: where it came from and what it was called."""

    ref: str
    branch: str
    message: str
    formatted_date: str = ""
