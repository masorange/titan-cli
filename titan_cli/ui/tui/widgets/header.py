"""
Header Widget

Custom header widget with title and back button.
"""
from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import Static
from textual.containers import Horizontal
from textual.reactive import reactive
from textual.message import Message

from titan_cli import __version__
from titan_cli.ui.tui.icons import Icons


class HeaderWidget(Widget):
    """
    Header widget that displays screen title and back button.

    Shows:
    - Left: Back button (← Back)
    - Center: Screen title
    - Right: Empty (for symmetry)
    """

    # Reactive property for title
    title: reactive[str] = reactive("Titan CLI")

    DEFAULT_CSS = """
    HeaderWidget {
        background: $surface-lighten-1;
        height: 3;
        width: 100%;
        dock: top;
    }

    HeaderWidget Horizontal {
        width: 100%;
        height: 100%;
        align: center middle;
    }

    HeaderWidget #header-back {
        width: auto;
        min-width: 15;
        height: 100%;
        background: transparent;
        color: $primary;
        text-align: left;
        padding: 0 2;
        content-align: left middle;
    }

    HeaderWidget #header-back:hover {
        background: $surface-lighten-2;
        text-style: bold;
    }

    HeaderWidget #header-title {
        width: 1fr;
        height: 100%;
        content-align: center middle;
        text-align: center;
        color: $primary;
        text-style: bold;
    }

    HeaderWidget .header-left,
    HeaderWidget .header-right {
        width: auto;
        min-width: 15;
        height: 100%;
    }
    """

    def __init__(self, title: str = "Titan CLI", show_back: bool = True, show_version: bool = False, **kwargs):
        """
        Initialize header widget.

        Args:
            title: Title to display in header
            show_back: Whether to show back button
            show_version: Whether to show version in title
        """
        super().__init__(**kwargs)
        self.show_back = show_back
        self.show_version = show_version

        # Add version to title if requested and available
        if show_version:
            try:
                # Only show version if we can get it from installed package
                version_str = __version__
                if version_str and version_str != "unknown":
                    self.title = f"{title} {version_str}"
                else:
                    self.title = title
            except Exception:
                # If we can't get version, just show title without version
                self.title = title
        else:
            self.title = title

    def compose(self) -> ComposeResult:
        """Compose the header with back button and title."""
        with Horizontal():
            if self.show_back:
                yield Static(f"{Icons.BACK} Back", id="header-back", classes="header-left")
            else:
                yield Static("", classes="header-left")

            yield Static(self.title, id="header-title")
            yield Static("", classes="header-right")

    def on_click(self, event) -> None:
        """Handle click on header elements."""
        if event.widget.id == "header-back":
            # Post a message to the screen to go back
            self.post_message(self.BackPressed())

    def watch_title(self, new_value: str) -> None:
        """Update title display when title changes."""
        if self.is_mounted:
            try:
                title_widget = self.query_one("#header-title", Static)
                title_widget.update(new_value)
            except Exception:
                pass

    class BackPressed(Message):
        """Message sent when back button is pressed."""
        pass
