"""
Panel Widget

A bordered container for displaying important messages with different types.
"""

from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import Label, Markdown
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

    Panel Markdown {
        width: 100%;
        height: auto;
        background: transparent;
        padding: 0;
        margin: 0;
    }

    Panel Markdown MarkdownH1,
    Panel Markdown MarkdownH2,
    Panel Markdown MarkdownH3 {
        margin-top: 0;
    }

    Panel Markdown MarkdownParagraph {
        margin-bottom: 0;
    }

    Panel.markdown {
        width: 1fr;
    }

    Panel.markdown > Container {
        width: 1fr;
    }
    """

    def __init__(
        self,
        text: str,
        panel_type: str = "info",
        show_icon: bool = True,
        use_markdown: bool = False,
        **kwargs
    ):
        """
        Initialize panel.

        Args:
            text: Text to display
            panel_type: Type of panel (info, success, warning, error)
            show_icon: Whether to show the icon (default: True)
            use_markdown: Render content as markdown instead of plain text
        """
        super().__init__(**kwargs)
        self.text = text
        self.panel_type = panel_type
        self.show_icon = show_icon
        self.use_markdown = use_markdown

        self.add_class(panel_type)
        if use_markdown:
            self.add_class("markdown")

    def compose(self) -> ComposeResult:
        """Compose the panel with bordered container."""
        icons = {
            "info": Icons.INFO,
            "success": Icons.SUCCESS,
            "warning": Icons.WARNING,
            "error": Icons.ERROR,
        }
        icon = icons.get(self.panel_type, Icons.INFO)

        with Container():
            if self.use_markdown:
                prefix = f"{icon} " if self.show_icon and icon else ""
                yield Markdown(f"{prefix}{self.text}")
            else:
                text = f"{icon} {self.text}" if self.show_icon and icon else self.text
                yield Label(text)
