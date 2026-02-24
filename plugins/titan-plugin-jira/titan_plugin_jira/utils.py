"""
Utility Functions for Jira Plugin

Reusable validation and helper functions.
"""

from typing import Tuple, Optional


def validate_non_empty_text(text: Optional[str]) -> Tuple[bool, str, str]:
    """
    Validate that text is not empty.

    Args:
        text: Text to validate

    Returns:
        Tuple of (is_valid, cleaned_text, error_code)
        - is_valid: True if text is valid
        - cleaned_text: Stripped text
        - error_code: Error code if invalid ("empty", "none")
    """
    if text is None:
        return (False, "", "none")

    cleaned = text.strip()
    if not cleaned:
        return (False, "", "empty")

    return (True, cleaned, "")


def validate_numeric_selection(
    selection: str, min_value: int, max_value: int
) -> Tuple[bool, int, str]:
    """
    Validate numeric selection input.

    Args:
        selection: User input string
        min_value: Minimum valid value (inclusive)
        max_value: Maximum valid value (inclusive)

    Returns:
        Tuple of (is_valid, index, error_code)
        - is_valid: True if selection is valid
        - index: Zero-based index (selection - 1)
        - error_code: Error code if invalid ("not_a_number", "out_of_range")
    """
    try:
        num = int(selection)
    except (ValueError, TypeError):
        return (False, -1, "not_a_number")

    # Convert to zero-based index
    index = num - 1

    if index < 0 or index >= max_value:
        return (False, -1, "out_of_range")

    return (True, index, "")


def truncate_text(text: str, max_length: int, suffix: str = "...") -> str:
    """
    Truncate text to maximum length, adding suffix if truncated.

    Args:
        text: Text to truncate
        max_length: Maximum length (including suffix)
        suffix: Suffix to add if truncated (default: "...")

    Returns:
        Truncated text
    """
    if len(text) <= max_length:
        return text

    return text[: max_length - len(suffix)] + suffix


__all__ = [
    "validate_non_empty_text",
    "validate_numeric_selection",
    "truncate_text",
]
