"""
Tests for Input Validation Utilities

Tests for pure functions that validate user input.
"""

import pytest
from titan_plugin_jira.utils.input_validation import (
    validate_numeric_selection,
    validate_non_empty_text,
)


class TestValidateNumericSelection:
    """Tests for validate_numeric_selection function."""

    def test_valid_selection_first_item(self):
        """Should validate first item (1) correctly."""
        is_valid, index, error = validate_numeric_selection("1", 1, 5)
        assert is_valid is True
        assert index == 0  # Zero-based index
        assert error is None

    def test_valid_selection_last_item(self):
        """Should validate last item correctly."""
        is_valid, index, error = validate_numeric_selection("5", 1, 5)
        assert is_valid is True
        assert index == 4  # Zero-based index
        assert error is None

    def test_valid_selection_middle_item(self):
        """Should validate middle item correctly."""
        is_valid, index, error = validate_numeric_selection("3", 1, 5)
        assert is_valid is True
        assert index == 2  # Zero-based index
        assert error is None

    def test_selection_too_low(self):
        """Should reject selection below minimum."""
        is_valid, index, error = validate_numeric_selection("0", 1, 5)
        assert is_valid is False
        assert index is None
        assert error == "out_of_range"

    def test_selection_too_high(self):
        """Should reject selection above maximum."""
        is_valid, index, error = validate_numeric_selection("6", 1, 5)
        assert is_valid is False
        assert index is None
        assert error == "out_of_range"

    def test_non_numeric_input(self):
        """Should reject non-numeric input."""
        is_valid, index, error = validate_numeric_selection("abc", 1, 5)
        assert is_valid is False
        assert index is None
        assert error == "not_a_number"

    def test_empty_string(self):
        """Should reject empty string."""
        is_valid, index, error = validate_numeric_selection("", 1, 5)
        assert is_valid is False
        assert index is None
        assert error == "not_a_number"

    def test_negative_number(self):
        """Should reject negative numbers."""
        is_valid, index, error = validate_numeric_selection("-1", 1, 5)
        assert is_valid is False
        assert index is None
        assert error == "out_of_range"

    def test_decimal_number(self):
        """Should reject decimal numbers."""
        is_valid, index, error = validate_numeric_selection("2.5", 1, 5)
        assert is_valid is False
        assert index is None
        assert error == "not_a_number"

    def test_whitespace_with_number(self):
        """Should handle whitespace around number."""
        is_valid, index, error = validate_numeric_selection("  3  ", 1, 5)
        assert is_valid is True
        assert index == 2

    def test_single_item_range(self):
        """Should work with single-item range."""
        is_valid, index, error = validate_numeric_selection("1", 1, 1)
        assert is_valid is True
        assert index == 0

    def test_large_range(self):
        """Should work with large ranges."""
        is_valid, index, error = validate_numeric_selection("100", 1, 100)
        assert is_valid is True
        assert index == 99

    def test_none_input(self):
        """Should reject None input."""
        is_valid, index, error = validate_numeric_selection(None, 1, 5)
        assert is_valid is False
        assert index is None
        assert error == "not_a_number"


class TestValidateNonEmptyText:
    """Tests for validate_non_empty_text function."""

    def test_valid_text(self):
        """Should validate normal text."""
        is_valid, cleaned, error = validate_non_empty_text("Hello world")
        assert is_valid is True
        assert cleaned == "Hello world"
        assert error is None

    def test_text_with_leading_whitespace(self):
        """Should strip leading whitespace."""
        is_valid, cleaned, error = validate_non_empty_text("  Hello")
        assert is_valid is True
        assert cleaned == "Hello"
        assert error is None

    def test_text_with_trailing_whitespace(self):
        """Should strip trailing whitespace."""
        is_valid, cleaned, error = validate_non_empty_text("Hello  ")
        assert is_valid is True
        assert cleaned == "Hello"
        assert error is None

    def test_text_with_both_whitespace(self):
        """Should strip both leading and trailing whitespace."""
        is_valid, cleaned, error = validate_non_empty_text("  Hello world  ")
        assert is_valid is True
        assert cleaned == "Hello world"
        assert error is None

    def test_empty_string(self):
        """Should reject empty string."""
        is_valid, cleaned, error = validate_non_empty_text("")
        assert is_valid is False
        assert cleaned is None
        assert error == "empty_or_whitespace"

    def test_only_whitespace(self):
        """Should reject whitespace-only string."""
        is_valid, cleaned, error = validate_non_empty_text("   ")
        assert is_valid is False
        assert cleaned is None
        assert error == "empty_or_whitespace"

    def test_only_tabs(self):
        """Should reject tab-only string."""
        is_valid, cleaned, error = validate_non_empty_text("\t\t\t")
        assert is_valid is False
        assert cleaned is None
        assert error == "empty_or_whitespace"

    def test_only_newlines(self):
        """Should reject newline-only string."""
        is_valid, cleaned, error = validate_non_empty_text("\n\n\n")
        assert is_valid is False
        assert cleaned is None
        assert error == "empty_or_whitespace"

    def test_mixed_whitespace(self):
        """Should reject mixed whitespace."""
        is_valid, cleaned, error = validate_non_empty_text("  \t\n  ")
        assert is_valid is False
        assert cleaned is None
        assert error == "empty_or_whitespace"

    def test_none_input(self):
        """Should reject None input."""
        is_valid, cleaned, error = validate_non_empty_text(None)
        assert is_valid is False
        assert cleaned is None
        assert error == "empty_or_whitespace"

    def test_single_character(self):
        """Should accept single character."""
        is_valid, cleaned, error = validate_non_empty_text("x")
        assert is_valid is True
        assert cleaned == "x"
        assert error is None

    def test_special_characters(self):
        """Should accept special characters."""
        is_valid, cleaned, error = validate_non_empty_text("!@#$%^&*()")
        assert is_valid is True
        assert cleaned == "!@#$%^&*()"
        assert error is None

    def test_unicode_text(self):
        """Should accept unicode text."""
        is_valid, cleaned, error = validate_non_empty_text("Hello 世界 🌍")
        assert is_valid is True
        assert cleaned == "Hello 世界 🌍"
        assert error is None

    def test_multiline_text(self):
        """Should accept multiline text."""
        text = "Line 1\nLine 2\nLine 3"
        is_valid, cleaned, error = validate_non_empty_text(text)
        assert is_valid is True
        assert cleaned == text
        assert error is None

    def test_preserves_internal_whitespace(self):
        """Should preserve internal whitespace while stripping edges."""
        is_valid, cleaned, error = validate_non_empty_text("  Hello   world  ")
        assert is_valid is True
        assert cleaned == "Hello   world"  # Internal spaces preserved
        assert error is None
