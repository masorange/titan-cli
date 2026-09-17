"""
Base Screen

Base class for all Titan TUI screens with consistent layout.
"""
from textual.app import ComposeResult
from textual.screen import Screen

from titan_cli.core.config import TitanConfig
from titan_cli.ui.tui.widgets.status_bar import StatusBarWidget
from titan_cli.ui.tui.widgets.header import HeaderWidget
from titan_cli.core.result import ClientSuccess

class BaseScreen(Screen):
    """
    Base screen with consistent layout for all Titan screens.

    Provides:
    - Header (top)
    - Content area (middle) - to be defined by subclasses
    - StatusBar (bottom, above footer)
    - Footer (bottom)

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
        show_status_bar: bool = True,
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
            show_status_bar: Whether to show status bar at bottom
        """
        super().__init__(**kwargs)
        self.config = config
        self.screen_title = title
        self.show_back = show_back
        self.show_favorite = show_favorite
        self.is_favorite = is_favorite
        self.show_status_bar = show_status_bar

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

        # StatusBar with current config values (optional)
        if self.show_status_bar:
            status_bar = StatusBarWidget(id="status-bar")
            self._update_status_bar(status_bar)
            yield status_bar

    def refresh_status_bar(self) -> None:
        """Repaint this screen's status bar from current state, if it has one.

        Public counterpart to `_update_status_bar`, for callers holding the screen rather
        than the widget - the app does this when the session override changes, which is
        state no config reload would pick up.
        """
        if not self.show_status_bar:
            return
        try:
            self._update_status_bar(self.query_one("#status-bar", StatusBarWidget))
        except Exception:
            pass

    def _update_status_bar(self, status_bar: StatusBarWidget) -> None:
        """
        Update status bar with current config values.

        Args:
            status_bar: StatusBarWidget to update
        """
        from titan_cli.ai.constants import get_source_display_name
        # Get git status
        git_branch = "N/A"
        try:
            git_plugin = self.config.registry.ensure_initialized("git")
            if git_plugin and git_plugin.is_available():
                git_client = git_plugin.get_client()
                result = git_client.get_status()
                match result:
                    case ClientSuccess(data=git_status):
                        git_branch = git_status.branch
                    case _:
                        git_branch = "N/A"
        except Exception:
            pass

        ai_config = self.config.config.ai if self.config.config else None

        # F3 cell: the connection that answers, and with which model. A session override
        # takes it over and marks itself with a *, exactly as it does to the F2 cell.
        override = getattr(self.app, "ai_session_override", None)
        connection_id = (ai_config.default_connection if ai_config else None)
        if override is not None and override.connection:
            connection_id = override.connection

        ai_info = "F3 —"
        if ai_config and connection_id in ai_config.connections:
            connection_cfg = ai_config.connections[connection_id]
            source_name = get_source_display_name(
                connection_cfg.provider or connection_cfg.gateway_backend
            )
            model = connection_cfg.default_model or "default"
            if override is not None and override.model:
                model = override.model
            ai_info = f"F3 {source_name} / {model}"
            if override is not None and (override.connection or override.model):
                ai_info = f"{ai_info} *"

        # F2 cell: the CLI Titan runs, and the model pinned to it. An unset model reads as
        # "default" rather than blank - the CLI still has one, Titan just isn't choosing it.
        #
        # A session override takes the cell over and marks itself with a *, because it
        # outranks everything saved: showing the saved value while something else runs
        # would make the bar lie, and an override nobody can see is one they forget is on.
        cli_info = "F2 —"
        if ai_config and ai_config.default_cli:
            cli = ai_config.default_cli
            cli_info = f"F2 {cli} / {ai_config.cli_models.get(cli) or 'default'}"
        if override is not None and (override.cli or override.model):
            cli = override.cli or (ai_config.default_cli if ai_config else None) or "—"
            model = override.model or (
                ai_config.cli_models.get(cli) if ai_config and cli else None
            )
            cli_info = f"F2 {cli} / {model or 'default'} *"

        # Get project name directly from config
        project_name = self.config.get_project_name() or "N/A"

        # Update status bar
        status_bar.git_branch = git_branch
        status_bar.cli_info = cli_info
        status_bar.ai_info = ai_info
        status_bar.project_name = project_name

    def on_screen_resume(self) -> None:
        """Called when screen is resumed (e.g., after another screen is dismissed)."""
        # Refresh status bar with latest config values
        if self.show_status_bar:
            try:
                # Reload config from disk to get latest changes
                self.config.load()

                status_bar = self.query_one("#status-bar", StatusBarWidget)
                self._update_status_bar(status_bar)
            except Exception:
                pass  # Status bar might not be mounted yet

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
