"""
Text Widgets

Reusable text widgets with theme-based styling.
"""
from textual.widgets import Static


class DimText(Static):
    """Text widget with dim/muted styling."""

    DEFAULT_CSS = """
    DimText {
        color: $text-muted;
    }
    """


class BoldText(Static):
    """Text widget with bold styling."""

    DEFAULT_CSS = """
    BoldText {
        text-style: bold;
    }
    """


class PrimaryText(Static):
    """Text widget with primary color."""

    DEFAULT_CSS = """
    PrimaryText {
        color: $primary;
    }
    """


class BoldPrimaryText(Static):
    """Text widget with bold primary color."""

    DEFAULT_CSS = """
    BoldPrimaryText {
        color: $primary;
        text-style: bold;
    }
    """


class SuccessText(Static):
    """Text widget with success/green color."""

    DEFAULT_CSS = """
    SuccessText {
        color: $success;
    }
    """


class ErrorText(Static):
    """Text widget with error/red color."""

    DEFAULT_CSS = """
    ErrorText {
        color: $error;
    }
    """


class WarningText(Static):
    """Text widget with warning/yellow color."""

    DEFAULT_CSS = """
    WarningText {
        color: $warning;
    }
    """


class ItalicText(Static):
    """Text widget with italic styling."""

    DEFAULT_CSS = """
    ItalicText {
        text-style: italic;
    }
    """


class DimItalicText(Static):
    """Text widget with dim italic styling."""

    DEFAULT_CSS = """
    DimItalicText {
        color: $text-muted;
        text-style: italic;
    }
    """
