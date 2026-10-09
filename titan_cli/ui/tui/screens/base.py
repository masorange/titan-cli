"""
Base Screen

Base class for all Titan TUI screens with consistent layout.
"""
from textual.app import ComposeResult
from textual.screen import Screen

from titan_cli.core.config import TitanConfig
from titan_cli.ui.tui.widgets.dock import Dock, ai_cells
from titan_cli.ui.tui.widgets.header import HeaderWidget
from titan_cli.ui.tui.widgets.mod_side_panel import ModSidePanel
from titan_cli.core.result import ClientSuccess

class BaseScreen(Screen):
    """
    Base screen with consistent layout for all Titan screens.

    Provides:
    - Header (top)
    - Content area (middle) - to be defined by subclasses
    - Dock (bottom): launcher, mods' slots and status; every shortcut is listed by `?`

    Subclasses should override `compose_content()` to define their content.
    """

    CSS = """
    BaseScreen {
        background: $surface;
    }

    #screen-content {
        height: 1fr;
        overflow-y: auto;
    }
    """

    def __init__(
        self,
        config: TitanConfig,
        title: str = "Titan CLI",
        show_back: bool = False,
        show_favorite: bool = False,
        is_favorite: bool = False,
        show_dock: bool = True,
        **kwargs,
    ):
        """
        Initialize base screen.

        Args:
            config: TitanConfig instance
            title: Title to display in header
            show_back: Whether to show back button in header
            show_favorite: Whether to show favorite button in header
            is_favorite: Initial favorite state for the header button
            show_dock: Whether to show the dock at the bottom
        """
        super().__init__(**kwargs)
        self.config = config
        self.screen_title = title
        self.show_back = show_back
        self.show_favorite = show_favorite
        self.is_favorite = is_favorite
        self.show_dock = show_dock

    def compose(self) -> ComposeResult:
        """Compose the base screen layout."""
        # Header with title and optional back/favorite buttons
        yield HeaderWidget(
            title=self.screen_title,
            show_back=self.show_back,
            show_favorite=self.show_favorite,
            is_favorite=self.is_favorite,
        )

        # Content area - subclasses define this
        yield from self.compose_content()

        # Textual lays docked widgets out last-first: yielded before the dock,
        # the panel stops above it and the dock keeps the full width.
        yield ModSidePanel()

        if self.show_dock:
            yield Dock(id="dock")

    def on_mount(self) -> None:
        self.refresh_dock()

    def refresh_dock(self) -> None:
        """Repaint this screen's dock from current state, if it has one.

        The app calls this when the session override changes, which is state no config
        reload would pick up.
        """
        if not self.show_dock:
            return
        try:
            dock = self.query_one("#dock", Dock)
        except Exception:
            return  # not mounted yet; on_mount paints it
        # The fold is toggled on whichever screen is on top; one underneath catches up here.
        dock.show_collapsed(getattr(self.app, "dock_collapsed", False))

        # Get git status
        git_branch = ""
        try:
            git_plugin = self.config.registry.ensure_initialized("git")
            if git_plugin and git_plugin.is_available():
                git_client = git_plugin.get_client()
                result = git_client.get_status()
                match result:
                    case ClientSuccess(data=git_status):
                        git_branch = git_status.branch
                    case _:
                        git_branch = ""
        except Exception:
            pass

        ai_config = self.config.config.ai if self.config.config else None
        override = getattr(self.app, "ai_session_override", None)
        cli_info, ai_info = ai_cells(ai_config, override)
        project_name = self.config.get_project_name() or "N/A"
        dock.show_status(project_name, git_branch, cli_info, ai_info)
        dock.refresh_tiles()

    def on_screen_resume(self) -> None:
        """Called when screen is resumed (e.g., after another screen is dismissed)."""
        if self.show_dock:
            try:
                # Reload config from disk to get latest changes
                self.config.load()
            except Exception:
                pass
            self.refresh_dock()

    def on_header_widget_back_pressed(self, message: HeaderWidget.BackPressed) -> None:
        """Handle back button press from header."""
        self.action_go_back()

    def action_go_back(self) -> None:
        """Go back to previous screen. Override in subclasses if needed."""
        self.app.pop_screen()

    def on_header_widget_favorite_pressed(self, message: HeaderWidget.FavoritePressed) -> None:
        """Handle favorite button press from header."""
        self.action_toggle_favorite()

    def action_toggle_favorite(self) -> None:
        """Toggle favorite status for the screen's subject. Override in subclasses."""
        pass
