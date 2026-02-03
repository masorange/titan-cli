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

Note: All styling is defined globally in theme.py (TITAN_THEME_CSS).
Widget classes are used to apply the correct CSS selectors.
"""
from textual.widgets import Static


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


# Styled text widgets - styling defined globally in theme.py
class DimText(Static):
    """Text widget with dim/muted styling."""
    pass


class BoldText(Static):
    """Text widget with bold styling."""
    pass


class PrimaryText(Static):
    """Text widget with primary color."""
    pass


class BoldPrimaryText(Static):
    """Text widget with bold primary color."""
    pass


class SuccessText(Static):
    """Text widget with success/green color."""
    pass


class ErrorText(Static):
    """Text widget with error/red color."""
    pass


class WarningText(Static):
    """Text widget with warning/yellow color."""
    pass


class ItalicText(Static):
    """Text widget with italic styling."""
    pass


class DimItalicText(Static):
    """Text widget with dim italic styling."""
    pass
