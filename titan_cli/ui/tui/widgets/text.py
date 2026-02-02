"""
Text Widgets

Canonical text widgets with theme-based styling for use across the entire application.

All screens, steps, and core components should use these widgets to ensure consistent
styling that automatically adapts to the active theme.

Widgets:
- Text: Plain text without styling
- DimText: Muted/dimmed text
- BoldText: Bold text
- SuccessText: Success/green color (uses $success theme variable)
- ErrorText: Error/red color (uses $error theme variable)
- WarningText: Warning/yellow color (uses $warning theme variable)
- PrimaryText: Primary theme color (uses $primary theme variable)
- BoldPrimaryText: Bold text with primary color
- ItalicText: Italic text
- DimItalicText: Dim italic text

Usage in screens/core:
    from titan_cli.ui.tui.widgets import DimText, SuccessText
    self.mount(DimText("Loading..."))
    self.mount(SuccessText("Completed!"))

Usage in workflow steps via TextualComponents:
    ctx.textual.dim_text("Loading...")
    ctx.textual.success_text("Completed!")
"""
from textual.widgets import Static


# Shared CSS for all text styling - DRY principle
SHARED_TEXT_CSS = """
.dim, DimText, DimItalicText {
    color: $text-muted;
}

.bold, BoldText, BoldPrimaryText {
    text-style: bold;
}

.italic, ItalicText, DimItalicText {
    text-style: italic;
}

.primary, PrimaryText, BoldPrimaryText {
    color: $primary;
}

.success, SuccessText {
    color: $success;
}

.error, ErrorText {
    color: $error;
}

.warning, WarningText {
    color: $warning;
}
"""


class Text(Static):
    """
    Plain text widget without styling.

    For styled text, use specialized widgets:
    - DimText: Muted/dimmed text
    - BoldText: Bold text
    - SuccessText: Success/green color
    - ErrorText: Error/red color
    - WarningText: Warning/yellow color
    - PrimaryText: Primary theme color
    - ItalicText: Italic text

    Usage:
        text = Text("Hello, world!")
    """
    pass


# Convenience widgets - use shared CSS
class DimText(Static):
    """Text widget with dim/muted styling."""
    DEFAULT_CSS = SHARED_TEXT_CSS


class BoldText(Static):
    """Text widget with bold styling."""
    DEFAULT_CSS = SHARED_TEXT_CSS


class PrimaryText(Static):
    """Text widget with primary color."""
    DEFAULT_CSS = SHARED_TEXT_CSS


class BoldPrimaryText(Static):
    """Text widget with bold primary color."""
    DEFAULT_CSS = SHARED_TEXT_CSS


class SuccessText(Static):
    """Text widget with success/green color."""
    DEFAULT_CSS = SHARED_TEXT_CSS


class ErrorText(Static):
    """Text widget with error/red color."""
    DEFAULT_CSS = SHARED_TEXT_CSS


class WarningText(Static):
    """Text widget with warning/yellow color."""
    DEFAULT_CSS = SHARED_TEXT_CSS


class ItalicText(Static):
    """Text widget with italic styling."""
    DEFAULT_CSS = SHARED_TEXT_CSS


class DimItalicText(Static):
    """Text widget with dim italic styling."""
    DEFAULT_CSS = SHARED_TEXT_CSS
