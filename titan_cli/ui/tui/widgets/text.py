"""
Text Widgets

Reusable text widgets with theme-based styling.
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
    Reusable text widget with dynamic styling via CSS classes.

    Usage:
        # Create with initial style
        text = Text("Hello", style="bold")

        # Change style dynamically
        text.set_style("error")

        # Combine multiple styles
        text = Text("Hello", style="bold primary")

    Available styles:
        - dim: Muted/dimmed text
        - bold: Bold text
        - italic: Italic text
        - primary: Primary color
        - success: Success/green color
        - error: Error/red color
        - warning: Warning/yellow color
    """

    DEFAULT_CSS = SHARED_TEXT_CSS

    def __init__(self, renderable="", *, style: str = "", **kwargs):
        """
        Initialize text widget.

        Args:
            renderable: Text content
            style: Space-separated style classes (e.g., "bold primary")
            **kwargs: Additional Static arguments
        """
        # Add style classes to existing classes
        if style:
            existing_classes = kwargs.get("classes", "")
            if existing_classes:
                kwargs["classes"] = f"{existing_classes} {style}"
            else:
                kwargs["classes"] = style

        super().__init__(renderable, **kwargs)

    def set_style(self, *styles: str) -> None:
        """
        Set the text style(s), removing previous styles.

        Args:
            *styles: One or more style names to apply

        Example:
            text.set_style("bold", "error")
        """
        # Remove all style classes
        for cls in ["dim", "bold", "italic", "primary", "success", "error", "warning"]:
            self.remove_class(cls)

        # Add new styles
        for style in styles:
            if style:
                self.add_class(style)

    def add_style(self, *styles: str) -> None:
        """
        Add style(s) to the text without removing existing ones.

        Args:
            *styles: One or more style names to add

        Example:
            text.add_style("italic")
        """
        for style in styles:
            if style:
                self.add_class(style)

    def remove_style(self, *styles: str) -> None:
        """
        Remove style(s) from the text.

        Args:
            *styles: One or more style names to remove

        Example:
            text.remove_style("bold")
        """
        for style in styles:
            if style:
                self.remove_class(style)


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
