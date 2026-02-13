"""
PR Creation Operations

Pure business logic for PR creation functionality.
These functions can be used by any step and are easily testable.
"""

from typing import List, Optional


def determine_pr_assignees(
    auto_assign: bool,
    current_user: str,
    existing_assignees: Optional[List[str]] = None
) -> List[str]:
    """
    Determine the assignees for a PR based on auto-assign setting.

    Args:
        auto_assign: Whether to automatically assign the current user
        current_user: The current GitHub username
        existing_assignees: Any existing assignees (default: empty list)

    Returns:
        List of assignee usernames

    Examples:
        >>> determine_pr_assignees(True, "alice", [])
        ['alice']
        >>> determine_pr_assignees(True, "alice", ["bob"])
        ['bob', 'alice']
        >>> determine_pr_assignees(False, "alice", ["bob"])
        ['bob']
        >>> determine_pr_assignees(True, "alice", ["alice"])
        ['alice']
    """
    assignees = existing_assignees.copy() if existing_assignees else []

    if auto_assign and current_user not in assignees:
        assignees.append(current_user)

    return assignees


def add_assignee_if_missing(
    assignee: str,
    existing_assignees: Optional[List[str]] = None
) -> List[str]:
    """
    Add an assignee to the list if not already present.

    Args:
        assignee: The username to add
        existing_assignees: Current list of assignees (default: empty list)

    Returns:
        Updated list of assignees

    Examples:
        >>> add_assignee_if_missing("alice", [])
        ['alice']
        >>> add_assignee_if_missing("alice", ["bob"])
        ['bob', 'alice']
        >>> add_assignee_if_missing("alice", ["alice"])
        ['alice']
    """
    assignees = existing_assignees.copy() if existing_assignees else []

    if assignee not in assignees:
        assignees.append(assignee)

    return assignees


__all__ = [
    "determine_pr_assignees",
    "add_assignee_if_missing",
]
