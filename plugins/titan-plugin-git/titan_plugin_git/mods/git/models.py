"""What the pane shows: the snapshots `read_repo` and `read_branches` build from the git plugin's UI models and the drawing reads."""
from dataclasses import dataclass, field
from typing import List, Optional

from titan_plugin_git.models.view import UIGitBranch, UIGitCommit, UIGitWorktree


@dataclass(frozen=True)
class Repo:
    branch: str
    has_upstream: bool = False
    ahead: int = 0
    behind: int = 0
    added: int = 0
    removed: int = 0
    commits: List[UIGitCommit] = field(default_factory=list)
    error: Optional[str] = None


@dataclass(frozen=True)
class Branches:
    """
    The branches offered for switching, most recently used first.

    `blocked` is why the switch is refused right now (uncommitted work), None
    when the tree is clean: the buttons read it, so the pane and the
    `switch_branch` step refuse for exactly the same reason.
    """

    items: List[UIGitBranch] = field(default_factory=list)
    current: str = ""
    main_branch: str = ""  # the plugin's configured base branch, the usual merge source
    blocked: Optional[str] = None
    error: Optional[str] = None


@dataclass(frozen=True)
class Worktrees:
    """
    The repository's worktrees, with the two that must not be removed marked:
    `main_path` (git refuses it) and `current_path` (the one Titan runs in).
    """

    items: List[UIGitWorktree] = field(default_factory=list)
    main_path: str = ""
    current_path: str = ""
    error: Optional[str] = None
