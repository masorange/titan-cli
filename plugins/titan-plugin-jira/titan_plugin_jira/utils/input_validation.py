"""
Input validation utilities.

Pure functions for validating user input.
"""


def validate_numeric_selection(
    selection: str, min_value: int, max_value: int
) -> tuple[bool, int | None, str | None]:
    """
    Validate numeric input selection.

    Args:
        selection: User input string
        min_value: Minimum valid value (inclusive)
        max_value: Maximum valid value (inclusive)

    Returns:
        Tuple of (is_valid, index, error_message)
        - is_valid: True if selection is valid
        - index: Zero-based index if valid, None otherwise
        - error_message: Error description if invalid, None otherwise

    Examples:
        >>> validate_numeric_selection("2", 1, 5)
        (True, 1, None)

        >>> validate_numeric_selection("10", 1, 5)
        (False, None, "out_of_range")

        >>> validate_numeric_selection("abc", 1, 5)
        (False, None, "not_a_number")
    """
    try:
        value = int(selection)
        index = value - 1

        if index < 0 or index >= max_value:
            return False, None, "out_of_range"

        return True, index, None

    except (ValueError, TypeError):
        return False, None, "not_a_number"


def validate_non_empty_text(text: str | None) -> tuple[bool, str | None, str | None]:
    """
    Validate that text is not empty or whitespace-only.

    Args:
        text: Input text to validate

    Returns:
        Tuple of (is_valid, cleaned_text, error_message)
        - is_valid: True if text is valid
        - cleaned_text: Stripped text if valid, None otherwise
        - error_message: Error description if invalid, None otherwise

    Examples:
        >>> validate_non_empty_text("hello")
        (True, "hello", None)

        >>> validate_non_empty_text("  ")
        (False, None, "empty_or_whitespace")

        >>> validate_non_empty_text(None)
        (False, None, "empty_or_whitespace")
    """
    if not text or not text.strip():
        return False, None, "empty_or_whitespace"

    return True, text.strip(), None
