"""
Branch Operations

Pure business logic for Git branch management.
These functions can be used by any step and are easily testable.
"""

import re
from typing import List, Optional, Sequence

from ..models.view.branch import UIGitBranch
from ..models.view.status import UIGitStatus

_CHECKOUT_MESSAGE = re.compile(r"^checkout: moving from (?P<from>.+?) to (?P<to>.+)$")


def check_branch_exists(branch_name: str, all_branches: List[str]) -> bool:
    """
    Check if a branch exists in the list of branches.

    Args:
        branch_name: Name of the branch to check
        all_branches: List of all branch names

    Returns:
        True if branch exists, False otherwise

    Examples:
        >>> check_branch_exists("main", ["main", "develop", "feature/new"])
        True
        >>> check_branch_exists("nonexistent", ["main", "develop"])
        False
        >>> check_branch_exists("main", [])
        False
    """
    return branch_name in all_branches


def determine_safe_checkout_target(
    current_branch: str,
    branch_to_delete: str,
    main_branch: str,
    all_branches: List[str]
) -> Optional[str]:
    """
    Determine a safe branch to checkout before deleting the current branch.

    Returns the main branch if available and different from the target,
    otherwise None (cannot safely delete).

    Args:
        current_branch: Currently checked out branch
        branch_to_delete: Branch that will be deleted
        main_branch: Name of the main branch (e.g., "main" or "master")
        all_branches: List of all available branches

    Returns:
        Safe branch name to checkout, or None if no safe option

    Examples:
        >>> determine_safe_checkout_target("feature", "feature", "main", ["main", "feature"])
        'main'
        >>> determine_safe_checkout_target("main", "main", "main", ["main"])

        >>> determine_safe_checkout_target("feature", "other", "main", ["main", "feature", "other"])

        >>> determine_safe_checkout_target("feature", "feature", "main", ["feature"])

    """
    # Only need to checkout if we're on the branch being deleted
    if current_branch != branch_to_delete:
        return None

    # Check if main branch exists and is different from the branch to delete
    if main_branch in all_branches and main_branch != branch_to_delete:
        return main_branch

    # No safe target available
    return None


def should_delete_before_create(
    branch_exists: bool,
    delete_if_exists: bool
) -> bool:
    """
    Determine if a branch should be deleted before creating a new one.

    Args:
        branch_exists: Whether the branch already exists
        delete_if_exists: Whether deletion is requested

    Returns:
        True if branch should be deleted, False otherwise

    Examples:
        >>> should_delete_before_create(True, True)
        True
        >>> should_delete_before_create(True, False)
        False
        >>> should_delete_before_create(False, True)
        False
        >>> should_delete_before_create(False, False)
        False
    """
    return branch_exists and delete_if_exists


def parse_checkout_targets(reflog: str) -> List[str]:
    """
    The branches HEAD was moved to, newest first and each one only once, read from
    `git reflog`'s subjects ("checkout: moving from X to Y"). A detached checkout
    leaves a commit hash there, which is not a branch name any caller can use, but
    telling the two apart is the caller's job: it has the branch list, this does not.
    """
    visited: List[str] = []
    for line in reflog.splitlines():
        match = _CHECKOUT_MESSAGE.match(line.strip())
        if not match:
            continue
        target = match.group("to").strip()
        if target and target not in visited:
            visited.append(target)
    return visited


def order_branches_by_use(
    branches: Sequence[UIGitBranch],
    visited: Sequence[str],
    limit: Optional[int] = None,
) -> List[UIGitBranch]:
    """
    Order branches by how recently they were worked on: the ones HEAD was switched
    to first, in `visited` order, then the rest as given (callers pass them sorted by
    last commit). The current branch always leads, so the pane never hides where you are.

    Args:
        branches: Branches to order
        visited: Branch names newest-visit-first, from `parse_checkout_targets`
        limit: Keep at most this many; None keeps all

    Returns:
        The ordered branches, each appearing once
    """
    by_name = {b.name: b for b in branches}
    ordered: List[UIGitBranch] = []

    current = next((b for b in branches if b.is_current), None)
    if current:
        ordered.append(current)

    for name in visited:
        branch = by_name.get(name)
        if branch and branch not in ordered:
            ordered.append(branch)

    for branch in branches:
        if branch not in ordered:
            ordered.append(branch)

    return ordered[:limit] if limit else ordered


def filter_branches(branches: Sequence[UIGitBranch], query: str) -> List[UIGitBranch]:
    """Branches whose name contains `query`, ignoring case. An empty query keeps them all."""
    needle = (query or "").strip().lower()
    if not needle:
        return list(branches)
    return [b for b in branches if needle in b.name.lower()]


def merge_sources(
    branches: Sequence[UIGitBranch], target: str, main_branch: str
) -> List[UIGitBranch]:
    """
    The branches that can be merged into `target`, the project's base branch first.

    Merging the base branch in is by far the common case, so it leads the list
    instead of waiting for its turn in recency order. `target` itself is left
    out: a branch cannot be merged into itself.

    Args:
        branches: Branches to choose from, in the order they were read
        target: Branch receiving the merge
        main_branch: The project's configured base branch, "" when there is none

    Returns:
        The candidates, base branch first, the rest in the given order
    """
    candidates = [b for b in branches if b.name != target]
    main = (main_branch or "").strip()
    if not main:
        return candidates
    return (
        [b for b in candidates if b.name == main]
        + [b for b in candidates if b.name != main]
    )


def push_rejected_hint(error: str) -> Optional[str]:
    """
    What to tell the user when git refused a push, or None when it failed for
    another reason.

    A rejected push means the remote has commits the local branch does not, so
    only a force push would land it - and that throws the remote's commits away.
    The pane never runs one: it says so and leaves the call to the user.

    Args:
        error: The message git printed

    Returns:
        A one-line hint, or None when the refusal was not a rejection
    """
    lowered = (error or "").lower()
    rejected = "rejected" in lowered or "non-fast-forward" in lowered or "fetch first" in lowered
    if not rejected:
        return None
    return "The remote has commits yours does not - pull first, or force push by hand if you mean to replace them."


def switching_blocked_by(status: UIGitStatus) -> Optional[str]:
    """
    Why the working tree cannot be left behind, or None when switching is safe.

    Modified and staged files block: switching would carry them onto the other branch.
    Untracked files do not - git keeps them wherever you go and never refuses the
    checkout over them.

    Args:
        status: The repository status

    Returns:
        A one-line reason to show the user, or None
    """
    pending = {*status.modified_files, *status.staged_files}
    if not pending:
        return None
    noun = "file" if len(pending) == 1 else "files"
    return f"{len(pending)} uncommitted {noun} - commit or stash before switching"


__all__ = [
    "check_branch_exists",
    "parse_checkout_targets",
    "order_branches_by_use",
    "filter_branches",
    "switching_blocked_by",
    "determine_safe_checkout_target",
    "should_delete_before_create",
]
