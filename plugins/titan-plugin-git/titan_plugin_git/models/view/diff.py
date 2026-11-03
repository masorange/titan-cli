"""UI model for per-file diff churn - pre-formatted for display."""
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class UIFileChurn:
    """
    UI model for one file's change counters in a diff.

    Binary files have no line counters (`git diff --numstat` prints "-"),
    so `is_binary` is True and both counters are 0.
    """

    path: str
    additions: int
    deletions: int
    is_binary: bool = False

    @property
    def total_changes(self) -> int:
        return self.additions + self.deletions


@dataclass
class UIFileChange:
    """
    UI model for one changed file in a commit or in the working tree.

    `status` is git's one-letter state: A added, M modified, D deleted, ? untracked.
    Binary files carry zero counters and `is_binary=True`.
    """

    path: str
    status: str
    additions: int = 0
    deletions: int = 0
    is_binary: bool = False


@dataclass
class UIUncommittedFiles:
    """The files that differ from HEAD, kept apart the way git keeps them: index and working tree."""

    staged: List[UIFileChange] = field(default_factory=list)
    unstaged: List[UIFileChange] = field(default_factory=list)  # untracked files included, status "?"


@dataclass(frozen=True)
class UIDiffLine:
    """
    One line of a hunk. `kind` is `add`, `del`, `context` or `no_newline` (git's
    "\\ No newline at end of file" marker). A line has the number it carries on the
    side it exists on: `old_no` for `del`, `new_no` for `add`, both for `context`.
    """

    kind: str
    text: str
    old_no: Optional[int] = None
    new_no: Optional[int] = None


@dataclass(frozen=True)
class UIDiffHunk:
    """A `@@` block: its header (with the section text git appends) and its lines."""

    header: str
    lines: List[UIDiffLine] = field(default_factory=list)


@dataclass
class UIFileDiff:
    """One file's diff, parsed into hunks. A binary file has no hunks and `is_binary=True`."""

    path: str
    hunks: List[UIDiffHunk] = field(default_factory=list)
    is_binary: bool = False

    @property
    def additions(self) -> int:
        return sum(1 for h in self.hunks for line in h.lines if line.kind == "add")

    @property
    def deletions(self) -> int:
        return sum(1 for h in self.hunks for line in h.lines if line.kind == "del")
