"""
AI Configuration Screen

Screen for managing AI connections (list, add, set default, test, delete).
"""

from textual.app import ComposeResult
from textual.widgets import Static, LoadingIndicator
from textual.containers import Container, Horizontal, VerticalScroll, Grid
from textual.binding import Binding
from textual.screen import ModalScreen

from titan_cli.ui.tui.icons import Icons
from titan_cli.ui.tui.widgets import DimText, Button, SuccessText, ErrorText
from .base import BaseScreen


class TestConnectionModal(ModalScreen):
    """Modal screen for testing an AI connection."""

    DEFAULT_CSS = """
    TestConnectionModal {
        align: center middle;
    }

    #test-modal-container {
        width: 70;
        height: auto;
        background: $surface-lighten-1;
        border: solid $primary;
        padding: 2;
    }

    #test-modal-header {
        text-style: bold;
        text-align: center;
        margin-bottom: 2;
    }

    #test-modal-content {
        height: auto;
        min-height: 15;
        align: center middle;
    }

    #test-modal-buttons {
        height: auto;
        align: center middle;
        margin-top: 2;
    }

    #loading-container {
        width: 100%;
        height: auto;
        align: center middle;
    }

    LoadingIndicator {
        height: 5;
        margin: 2 0;
    }

    .center-text {
        text-align: center;
        width: 100%;
    }
    """

    BINDINGS = [
        Binding("escape", "close_modal", "Close"),
    ]

    def __init__(self, connection_id: str, connection_cfg, config, **kwargs):
        super().__init__(**kwargs)
        self.connection_id = connection_id
        self.connection_cfg = connection_cfg
        self.config = config

    def compose(self) -> ComposeResult:
        """Compose the test modal."""
        with Container(id="test-modal-container"):
            yield Static(
                f"{Icons.SETTINGS} Testing connection: {self.connection_cfg.name}",
                id="test-modal-header",
            )
            yield Container(id="test-modal-content")
            with Container(id="test-modal-buttons"):
                yield Button("Close", variant="default", id="close-modal-button")

    def on_mount(self) -> None:
        """Start the test when modal mounts."""
        # Show loading indicator
        content = self.query_one("#test-modal-content", Container)

        # Mount loading indicator and text directly
        content.mount(LoadingIndicator())
        content.mount(
            DimText(
                f"\nTesting connection to {self.connection_cfg.name}...",
                classes="center-text",
            )
        )

        # Run test in background AFTER the UI has refreshed
        self.call_after_refresh(self._start_test)

    def _start_test(self) -> None:
        """Start the test after UI refresh."""
        self.run_worker(self._run_test(), exclusive=True)

    async def _run_test(self) -> None:
        """Run the test asynchronously."""
        import asyncio
        from titan_cli.core.secrets import SecretManager
        from titan_cli.ai.client import AIClient
        from titan_cli.ai.models import AIMessage

        content = self.query_one("#test-modal-content", Container)
        secrets = SecretManager()

        try:
            ai_client = AIClient(
                self.config.config.ai,
                secrets,
                provider_id=self.connection_id,
            )

            # Run the blocking generate call in a thread to keep UI responsive
            response = await asyncio.to_thread(
                ai_client.generate,
                messages=[AIMessage(role="user", content="Say 'Hello!' if you can hear me")],
            )

            # Show success - remove loading and show result
            content.remove_children()
            content.mount(SuccessText(f"{Icons.CHECK} Connection successful!\n\n"))

            model_info = (
                f" with model '{self.connection_cfg.model}'"
                if self.connection_cfg.model
                else ""
            )
            endpoint_info = (
                " (gateway endpoint)" if self.connection_cfg.base_url else ""
            )
            source_name = (
                self.connection_cfg.provider or self.connection_cfg.gateway_type
            )

            content.mount(
                DimText(
                    f"Connection: {source_name}{model_info}{endpoint_info}\n"
                )
            )
            content.mount(DimText(f"Model: {response.model}\n"))
            content.mount(DimText(f"\nResponse: {response.content}"))

        except Exception as e:
            # Show error - remove loading and show error
            content.remove_children()
            content.mount(ErrorText(f"{Icons.ERROR} Connection failed!\n\n"))
            content.mount(DimText(f"Error: {str(e)}"))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press."""
        if event.button.id == "close-modal-button":
            self.dismiss()

    def action_close_modal(self) -> None:
        """Close the modal."""
        self.dismiss()


class ConnectionCard(Container):
    """Widget showing a single AI connection with action buttons."""

    DEFAULT_CSS = """
    ConnectionCard {
        width: 100%;
        max-width: 60;
        height: auto;
        background: $surface-lighten-1;
        border: solid $accent;
        padding: 1 2;
    }

    ConnectionCard.default {
        border: solid $primary;
    }

    ConnectionCard .connection-name {
        text-style: bold;
    }

    ConnectionCard .connection-info {
        color: $text-muted;
    }

    ConnectionCard .button-row {
        height: auto;
        margin-top: 1;
    }
    """

    def __init__(
        self,
        connection_id: str,
        connection_cfg: dict,
        is_default: bool = False,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.connection_id = connection_id
        self.connection_cfg = connection_cfg
        self.is_default = is_default

    def compose(self) -> ComposeResult:
        """Compose the connection card."""
        import re

        clean_id = re.sub(r"[^a-z0-9_-]", "", self.connection_id.lower())

        name = self.connection_cfg.get("name", self.connection_id)
        default_marker = f"{Icons.STAR} " if self.is_default else ""
        yield Static(f"{default_marker}{name}", classes="connection-name")

        kind = self.connection_cfg.get("kind", "")
        provider = self.connection_cfg.get("provider")
        gateway_type = self.connection_cfg.get("gateway_type")
        source_label = provider or gateway_type or "unknown"
        model = self.connection_cfg.get(
            "default_model", self.connection_cfg.get("model", "")
        )

        yield DimText(f"Type: {kind}", classes="connection-info")
        yield DimText(f"Source: {source_label}", classes="connection-info")
        yield DimText(f"Model: {model}", classes="connection-info")

        base_url = self.connection_cfg.get("base_url")
        if base_url:
            yield DimText(f"Base URL: {base_url}", classes="connection-info")
        else:
            yield DimText(" ", classes="connection-info")

        # Action buttons (use cleaned ID for button IDs)
        with Horizontal(classes="button-row"):
            if not self.is_default:
                yield Button("Set Default", variant="primary", id=f"set-default-{clean_id}")
            yield Button("Test Connection", variant="default", id=f"test-{clean_id}")
            yield Button("Delete", variant="error", id=f"delete-{clean_id}")


class AIConfigScreen(BaseScreen):
    """
    Screen for AI connection configuration and management.
    """

    BINDINGS = [
        Binding("escape", "back", "Back"),
    ]

    CSS = """
    AIConfigScreen {
        align: center middle;
    }

    #config-container {
        width: 85%;
        height: 1fr;
        background: $surface-lighten-1;
        padding: 0 2 1 2;
        margin: 1 0 1 0;
    }

    #providers-scroll {
        height: 1fr;
        padding: 1 0;
        align: center top;
        overflow-y: auto;
    }

    #providers-grid {
        grid-size: 2;
        grid-gutter: 2;
        width: 70%;
        height: auto;
    }

    #no-providers {
        text-align: center;
        color: $text-muted;
        margin: 8 0;
        column-span: 2;
    }

    #add-provider-container {
        height: auto;
        padding: 0 0;
        align: center middle;
    }
    """

    def __init__(self, config):
        super().__init__(
            config,
            title=f"{Icons.AI_CONFIG} AI Configuration",
            show_back=True
        )

    def compose_content(self) -> ComposeResult:
        """Compose the AI configuration screen."""
        with Container(id="config-container"):
            # Scrollable area with grid for connections
            with VerticalScroll(id="providers-scroll"):
                yield Grid(id="providers-grid")

            # Add connection button at the bottom
            with Container(id="add-provider-container"):
                yield Button(
                    f"{Icons.SETTINGS} New Connection",
                    variant="primary",
                    id="add-provider-button",
                )

    def on_mount(self) -> None:
        """Load connections when mounted."""
        self.load_connections()

    def on_screen_resume(self) -> None:
        """Reload connections when returning from wizard."""
        self.load_connections()
        self._refresh_status_bar()

    def _refresh_status_bar(self) -> None:
        """Refresh the status bar with current AI info."""
        try:
            from titan_cli.ui.tui.widgets import StatusBarWidget
            status_bar = self.query_one(StatusBarWidget)
            self._update_status_bar(status_bar)
        except Exception:
            pass  # Status bar might not be available

    def load_connections(self) -> None:
        """Load and display all configured AI connections."""
        # Reload config to get latest
        self.config.load()

        # Get the grid
        try:
            grid = self.query_one("#providers-grid", Grid)
        except Exception:
            # Grid was removed, recreate it
            scroll = self.query_one("#providers-scroll", VerticalScroll)
            # Remove no-providers message if it exists
            try:
                no_prov = self.query_one("#no-providers", Static)
                no_prov.remove()
            except Exception:
                pass
            grid = Grid(id="providers-grid")
            scroll.mount(grid)

        grid.remove_children()

        if not self.config.config.ai or not self.config.config.ai.connections:
            # Remove any existing no-providers message first
            try:
                existing = self.query_one("#no-providers", Static)
                existing.remove()
            except Exception:
                pass

            # Show no providers message
            grid.mount(Static(
                "No AI connections configured yet.\n\n"
                "Click 'New Connection' to configure your first connection.",
                id="no-providers"
            ))
            return

        default_id = self.config.config.ai.default_connection

        for connection_id, connection_cfg in self.config.config.ai.connections.items():
            is_default = connection_id == default_id
            card = ConnectionCard(
                connection_id=connection_id,
                connection_cfg=connection_cfg.model_dump(),
                is_default=is_default
            )
            if is_default:
                card.add_class("default")
            grid.mount(card)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        button_id = event.button.id

        if button_id == "add-provider-button":
            self.handle_add_connection()
        elif button_id.startswith("set-default-") or button_id.startswith("test-") or button_id.startswith("delete-"):
            card = event.button.parent.parent
            if isinstance(card, ConnectionCard):
                connection_id = card.connection_id

                if button_id.startswith("set-default-"):
                    self.handle_set_default(connection_id)
                elif button_id.startswith("test-"):
                    self.handle_test_connection(connection_id)
                elif button_id.startswith("delete-"):
                    self.handle_delete(connection_id)

    def handle_add_connection(self) -> None:
        """Open the configuration wizard to add a new connection."""
        from .ai_config_wizard import AIConfigWizardScreen

        self.app.push_screen(AIConfigWizardScreen(self.config))

    def handle_set_default(self, connection_id: str) -> None:
        """Set a connection as default."""

        try:
            self.config.set_default_ai_connection(connection_id)

            self.config.load()
            self.load_connections()
            self._refresh_status_bar()

            connection_name = self.config.config.ai.connections[connection_id].name
            self.app.notify(
                f"'{connection_name}' is now the default connection",
                severity="information",
            )

        except Exception as e:
            self.app.notify(f"Failed to set default: {e}", severity="error")

    def handle_test_connection(self, connection_id: str) -> None:
        """Test connection to an AI connection."""
        self.config.load()

        if connection_id not in self.config.config.ai.connections:
            self.app.notify("Connection not found", severity="error")
            return

        connection_cfg = self.config.config.ai.connections[connection_id]
        self.app.push_screen(
            TestConnectionModal(connection_id, connection_cfg, self.config)
        )

    def handle_delete(self, connection_id: str) -> None:
        """Delete an AI connection."""
        from titan_cli.core.secrets import SecretManager

        try:
            self.config.load()

            if connection_id not in self.config.config.ai.connections:
                self.app.notify("Connection not found", severity="error")
                return

            connection_name = self.config.config.ai.connections[connection_id].name
            self.config.delete_ai_connection(connection_id)

            secrets = SecretManager()
            try:
                secrets.delete(f"{connection_id}_api_key", scope="user")
            except Exception:
                pass

            self.config.load()
            self.load_connections()
            self._refresh_status_bar()

            self.app.notify(
                f"Connection '{connection_name}' deleted",
                severity="information",
            )

        except Exception as e:
            self.app.notify(f"Failed to delete provider: {e}", severity="error")

    def action_back(self) -> None:
        """Go back to main menu (ESC key)."""
        self.dismiss()

    def action_go_back(self) -> None:
        """Go back to main menu (Back button)."""
        self.dismiss()
