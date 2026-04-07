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
    """
    try:
        value = int(selection)

        if value < min_value or value > max_value:
            return False, None, "out_of_range"

        index = value - min_value  # Convert to zero-based index
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
    """
    if not text or not text.strip():
        return False, None, "empty_or_whitespace"

    return True, text.strip(), None
