"""
Branch Operations

Pure business logic for Git branch management.
These functions can be used by any step and are easily testable.
"""

from typing import List, Optional


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


__all__ = [
    "check_branch_exists",
    "determine_safe_checkout_target",
    "should_delete_before_create",
]
