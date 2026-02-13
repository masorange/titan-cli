"""
PanelContainer Widget

Base container with border and padding that accepts child widgets.
Reusable component for StepContainer, CommentThread, and other bordered widgets.
"""

from textual.containers import VerticalScroll


class PanelContainer(VerticalScroll):
    """
    Base panel container with bordered box and theme-based styling.

    This is the base component for all bordered containers in Titan TUI.
    Accepts child widgets and provides consistent border/padding/theme.

    Variants:
    - default: Primary border color
    - success: Green border
    - error: Red border
    - warning: Yellow border
    - info: Accent border
    """

    DEFAULT_CSS = """
    PanelContainer {
        width: 100%;
        height: auto;
        border: round $primary;
        padding: 1 2;
        margin: 1 0;
    }

    PanelContainer.default {
        border: round $primary;
    }

    PanelContainer.success {
        border: round $success;
    }

    PanelContainer.error {
        border: round $error;
    }

    PanelContainer.warning {
        border: round $warning;
    }

    PanelContainer.info {
        border: round $accent;
    }

    PanelContainer > Static {
        color: initial;
    }
    """

    def __init__(self, variant: str = "default", title: str = None, **kwargs):
        """
        Initialize panel container.

        Args:
            variant: Style variant (default, success, error, warning, info)
            title: Optional border title
        """
        super().__init__(**kwargs)

        # Set border title if provided
        if title:
            self.border_title = title

        # Add variant class
        self.add_class(variant)

    def set_variant(self, variant: str):
        """
        Change the panel variant (updates border color).

        Args:
            variant: One of 'default', 'success', 'error', 'warning', 'info'
        """
        # Remove all variant classes
        self.remove_class("default", "success", "error", "warning", "info")

        # Add new variant
        if variant in ["default", "success", "error", "warning", "info"]:
            self.add_class(variant)
        else:
            self.add_class("default")


__all__ = ["PanelContainer"]
