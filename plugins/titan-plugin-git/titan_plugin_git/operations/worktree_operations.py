"""
Worktree Operations

Pure business logic for working with git worktrees.
These functions are UI-agnostic and easily testable.
"""

import os
from typing import List, Optional, Sequence

from ..models.view.worktree import UIGitWorktree


def main_worktree_path(worktrees: Sequence[UIGitWorktree]) -> str:
    """
    The repository's main worktree: the first one `git worktree list` prints.

    Args:
        worktrees: Worktrees as the client returned them, in git's own order

    Returns:
        Its path, or "" when there are none
    """
    return worktrees[0].path if worktrees else ""


def removal_blocked_by(
    worktree: UIGitWorktree,
    main_path: str,
    current_path: str,
) -> Optional[str]:
    """
    Why a worktree cannot be removed, or None when it can.

    Git itself refuses the main worktree, and removing the one you are working
    in would pull the floor from under the running session, so both are refused
    before anything is offered.

    Args:
        worktree: The worktree in question
        main_path: Path of the main worktree
        current_path: Path Titan is running in

    Returns:
        A one-line reason to show the user, or None
    """
    if worktree.is_bare:
        return "the bare repository"
    if same_path(worktree.path, main_path):
        return "the main worktree"
    if same_path(worktree.path, current_path):
        return "the worktree you are in"
    return None


def same_path(a: str, b: str) -> bool:
    """Whether two paths point at the same place, symlinks and trailing slashes aside."""
    if not a or not b:
        return False
    return os.path.realpath(a) == os.path.realpath(b)


def removable_worktrees(
    worktrees: Sequence[UIGitWorktree],
    current_path: str,
) -> List[UIGitWorktree]:
    """The worktrees `removal_blocked_by` lets go, in the order given."""
    main_path = main_worktree_path(worktrees)
    return [w for w in worktrees if removal_blocked_by(w, main_path, current_path) is None]


__all__ = [
    "main_worktree_path",
    "removal_blocked_by",
    "same_path",
    "removable_worktrees",
]
