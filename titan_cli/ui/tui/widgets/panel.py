"""
Panel Widget

A bordered container for displaying important messages with different types.
"""

from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import Label
from textual.containers import Container

from titan_cli.ui.tui.icons import Icons


class Panel(Widget):
    """Panel widget with border and type-based styling."""

    DEFAULT_CSS = """
    Panel {
        width: auto;
        height: auto;
        margin: 0 0 1 0;
    }

    Panel > Container {
        width: auto;
        height: auto;
        border: round $primary;
        padding: 1;
    }

    Panel.info > Container {
        border: round $accent;
    }

    Panel.success > Container {
        border: round $success;
    }

    Panel.warning > Container {
        border: round $warning;
    }

    Panel.error > Container {
        border: round $error;
    }

    Panel Label {
        width: auto;
        height: auto;
    }
    """

    def __init__(self, text: str, panel_type: str = "info", show_icon: bool = True, **kwargs):
        """
        Initialize panel.

        Args:
            text: Text to display
            panel_type: Type of panel (info, success, warning, error)
            show_icon: Whether to show the icon (default: True)
        """
        super().__init__(**kwargs)
        self.text = text
        self.panel_type = panel_type
        self.show_icon = show_icon

        # Add CSS class based on type
        self.add_class(panel_type)

    def compose(self) -> ComposeResult:
        """Compose the panel with bordered container."""
        # Map panel types to icons from Icons class
        icons = {
            "info": Icons.INFO,
            "success": Icons.SUCCESS,
            "warning": Icons.WARNING,
            "error": Icons.ERROR,
        }

        icon = icons.get(self.panel_type, Icons.INFO)

        # Format text with or without icon
        if self.show_icon and icon:
            text = f"{icon} {self.text}"
        else:
            text = self.text

        with Container():
            yield Label(text)
