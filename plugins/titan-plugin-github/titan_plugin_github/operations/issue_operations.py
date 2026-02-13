"""
Issue Operations

Pure business logic for GitHub issue functionality.
These functions can be used by any step and are easily testable.
"""

from typing import List, Optional


def parse_comma_separated_list(input_string: str) -> List[str]:
    """
    Parse a comma-separated string into a list of trimmed non-empty items.

    Args:
        input_string: Comma-separated string (e.g., "bug, feature, help wanted")

    Returns:
        List of trimmed non-empty strings

    Examples:
        >>> parse_comma_separated_list("bug, feature, help wanted")
        ['bug', 'feature', 'help wanted']
        >>> parse_comma_separated_list("bug,feature,help wanted")
        ['bug', 'feature', 'help wanted']
        >>> parse_comma_separated_list("  bug  ,  , feature  ")
        ['bug', 'feature']
        >>> parse_comma_separated_list("")
        []
        >>> parse_comma_separated_list("   ")
        []
    """
    if not input_string or not input_string.strip():
        return []

    items = [item.strip() for item in input_string.split(",") if item.strip()]
    return items


def filter_valid_labels(
    selected_labels: List[str],
    available_labels: List[str]
) -> tuple[List[str], List[str]]:
    """
    Filter selected labels to separate valid and invalid ones.

    Args:
        selected_labels: Labels selected by the user
        available_labels: Labels that exist in the repository

    Returns:
        Tuple of (valid_labels, invalid_labels)

    Examples:
        >>> filter_valid_labels(["bug", "feature"], ["bug", "feature", "help"])
        (['bug', 'feature'], [])
        >>> filter_valid_labels(["bug", "invalid"], ["bug", "feature"])
        (['bug'], ['invalid'])
        >>> filter_valid_labels([], ["bug"])
        ([], [])
        >>> filter_valid_labels(["bug", "feature", "invalid"], ["bug"])
        (['bug'], ['feature', 'invalid'])
    """
    valid = []
    invalid = []

    for label in selected_labels:
        if label in available_labels:
            valid.append(label)
        else:
            invalid.append(label)

    return valid, invalid


def parse_assignees_and_labels(
    assignees_str: Optional[str],
    labels_str: Optional[str]
) -> tuple[List[str], List[str]]:
    """
    Parse assignees and labels from comma-separated strings.

    Args:
        assignees_str: Comma-separated assignees (or None)
        labels_str: Comma-separated labels (or None)

    Returns:
        Tuple of (assignees_list, labels_list)

    Examples:
        >>> parse_assignees_and_labels("alice, bob", "bug, feature")
        (['alice', 'bob'], ['bug', 'feature'])
        >>> parse_assignees_and_labels(None, "bug")
        ([], ['bug'])
        >>> parse_assignees_and_labels("alice", None)
        (['alice'], [])
        >>> parse_assignees_and_labels("", "")
        ([], [])
    """
    assignees = parse_comma_separated_list(assignees_str) if assignees_str else []
    labels = parse_comma_separated_list(labels_str) if labels_str else []

    return assignees, labels


__all__ = [
    "parse_comma_separated_list",
    "filter_valid_labels",
    "parse_assignees_and_labels",
]
