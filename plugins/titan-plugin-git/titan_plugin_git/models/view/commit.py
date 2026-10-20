"""UI model for Git commit - pre-formatted for display."""
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class UIGitCommit:
    """
    UI model for git commit - formatted for display.

    Contains pre-formatted data with icons and short hashes.
    """
    hash: str
    short_hash: str  # First 7 characters
    message: str
    message_subject: str  # First line of commit message
    author: str
    author_short: str  # Just name, no email
    date: str  # Raw date
    formatted_date: str  # Human-readable: "2 days ago" or "2026-01-15"
    pr_number: Optional[int] = None  # The PR a squash merge landed, from its "(#1234)" suffix
    parents: List[str] = field(default_factory=list)  # Full hashes; more than one means a merge
    refs: List[str] = field(default_factory=list)  # Branches and tags pointing here, "HEAD -> " stripped


@dataclass(frozen=True)
class UIGitGraphRow:
    """
    One drawn line of a commit graph: the lane glyphs and, for a commit row, the
    commit they belong to.

    A `link` row (no commit) carries only the edges that fork out of the commit
    above it, the way `git log --graph` draws them. `lane` is the column the
    commit sits in, -1 on a link row.
    """

    cells: tuple
    lane: int = -1
    commit: Optional[UIGitCommit] = None

    @property
    def is_link(self) -> bool:
        return self.commit is None
