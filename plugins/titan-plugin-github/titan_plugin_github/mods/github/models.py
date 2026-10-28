"""What the pane shows: snapshots the readers build from the github plugin's UI models and the drawing reads."""
from dataclasses import dataclass, field
from typing import List, Optional

from titan_plugin_github.models.view import UIMergeQueueEntry, UIPullRequest, UIWorkflowRun


@dataclass(frozen=True)
class Prs:
    repo: str = ""
    to_review: List[UIPullRequest] = field(default_factory=list)
    mine: List[UIPullRequest] = field(default_factory=list)
    open_count: int = 0
    error: Optional[str] = None


@dataclass(frozen=True)
class Others:
    """Every open PR of the repo, read on its own: the slow read must not hold back your PRs.

    The pane drops the ones that are already yours or waiting on you.
    """

    prs: List[UIPullRequest] = field(default_factory=list)
    error: Optional[str] = None


@dataclass(frozen=True)
class Queue:
    configured: bool = False
    branch: str = ""
    merge_method: str = ""
    total: int = 0
    entries: List[UIMergeQueueEntry] = field(default_factory=list)
    next_eta: str = ""
    error: Optional[str] = None


@dataclass(frozen=True)
class Threads:
    """How many review conversations of a PR are still open, once GitHub has been asked."""

    status: str  # "running", "done" or "error"
    unresolved: int = 0
    error: Optional[str] = None


@dataclass(frozen=True)
class Runs:
    """The latest workflow runs of the repo, newest first, as many as the pane has been asked for.

    `limit` is what the next read asks GitHub for: "show more" raises it.
    """

    runs: List[UIWorkflowRun] = field(default_factory=list)
    limit: int = 10
    error: Optional[str] = None


@dataclass(frozen=True)
class Composer:
    """What is being written in the pane right now, and the PR it answers."""

    number: int
    kind: str  # the only one with a field of its own: "comment"
    text: str = ""


@dataclass(frozen=True)
class Conflicts:
    """What clashes between a PR and its base branch, once git has been asked."""

    status: str  # "running", "done" or "error"
    files: List[str] = field(default_factory=list)
    error: Optional[str] = None
