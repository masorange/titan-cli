"""
AI Configuration Screen

Screen for managing AI providers (list, add, set default, test, delete).
"""

from textual.app import ComposeResult
from textual.widgets import Static
from textual.containers import Container, Horizontal, VerticalScroll, Grid
from textual.binding import Binding

from titan_cli.ui.tui.icons import Icons
from titan_cli.ui.tui.widgets import DimText, Button
from .base import BaseScreen
import tomli
import tomli_w
from titan_cli.core.config import TitanConfig


class ProviderCard(Container):
    """Widget showing a single AI provider with action buttons."""

    DEFAULT_CSS = """
    ProviderCard {
        width: 100%;
        max-width: 60;
        height: auto;
        background: $surface-lighten-1;
        border: solid $accent;
        padding: 1 2;
    }

    ProviderCard.default {
        border: solid $primary;
    }

    ProviderCard .provider-name {
        text-style: bold;
    }

    ProviderCard .provider-info {
        color: $text-muted;
    }

    ProviderCard .button-row {
        height: auto;
        margin-top: 1;
    }
    """

    def __init__(self, provider_id: str, provider_cfg: dict, is_default: bool = False, **kwargs):
        super().__init__(**kwargs)
        self.provider_id = provider_id
        self.provider_cfg = provider_cfg
        self.is_default = is_default

    def compose(self) -> ComposeResult:
        """Compose the provider card."""
        import re

        # Clean provider_id for use in button IDs (only allow valid characters)
        clean_id = re.sub(r'[^a-z0-9_-]', '', self.provider_id.lower())

        # Provider name with default indicator
        name = self.provider_cfg.get("name", self.provider_id)
        default_marker = f"{Icons.STAR} " if self.is_default else ""
        yield Static(f"{default_marker}{name}", classes="provider-name")

        # Provider details
        provider = self.provider_cfg.get("provider", "")
        provider_label = "Anthropic" if provider == "anthropic" else "Google" if provider == "gemini" else provider
        model = self.provider_cfg.get("model", "")

        yield DimText(f"Provider: {provider_label} (Claude)" if provider == "anthropic" else f"Provider: {provider_label} (Gemini)", classes="provider-info")
        yield DimText(f"Model: {model}", classes="provider-info")

        # Show base URL (always show this line for consistent height)
        base_url = self.provider_cfg.get("base_url")
        if base_url:
            yield DimText(f"Base URL: {base_url}", classes="provider-info")
        else:
            # Add empty line to maintain consistent height
            yield DimText(" ", classes="provider-info")

        # Show type
        config_type = self.provider_cfg.get("type", "")
        type_label = "Corporate" if config_type == "corporate" else "Individual"
        yield DimText(f"Type: {type_label}", classes="provider-info")

        # Action buttons (use cleaned ID for button IDs)
        with Horizontal(classes="button-row"):
            if not self.is_default:
                yield Button("Set Default", variant="primary", id=f"set-default-{clean_id}")
            yield Button("Test Connection", variant="default", id=f"test-{clean_id}")
            yield Button("Delete", variant="error", id=f"delete-{clean_id}")


class AIConfigScreen(BaseScreen):
    """
    Screen for AI provider configuration and management.
    """

    BINDINGS = [
        Binding("escape", "back", "Back"),
    ]

    CSS = """
    AIConfigScreen {
        align: center middle;
    }

    #config-container {
        width: 90%;
        height: 1fr;
        background: $surface-lighten-1;
        padding: 0 2 1 2;
    }

    #providers-scroll {
        height: 1fr;
        padding: 1 0;
        align: center top;
    }

    #providers-grid {
        grid-size: 2;
        grid-gutter: 2;
        width: 100%;
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
        padding: 1 0;
        align: center middle;
    }
    """

    def __init__(self, config):
        super().__init__(
            config,
            title=f"{Icons.SETTINGS} AI Configuration",
            show_back=True
        )

    def compose_content(self) -> ComposeResult:
        """Compose the AI configuration screen."""
        with Container(id="config-container"):
            # Add provider button at the top
            with Container(id="add-provider-container"):
                yield Button(f"{Icons.SETTINGS} Add New Provider", variant="primary", id="add-provider-button")

            # Scrollable area with grid for providers
            with VerticalScroll(id="providers-scroll"):
                yield Grid(id="providers-grid")

    def on_mount(self) -> None:
        """Load providers when mounted."""
        self.load_providers()

    def on_screen_resume(self) -> None:
        """Reload providers when returning from wizard."""
        self.load_providers()
        # Update status bar in case a new provider was added
        self._refresh_status_bar()

    def _refresh_status_bar(self) -> None:
        """Refresh the status bar with current AI info."""
        try:
            from titan_cli.ui.tui.widgets import StatusBarWidget
            status_bar = self.query_one(StatusBarWidget)
            self._update_status_bar(status_bar)
        except Exception:
            pass  # Status bar might not be available

    def load_providers(self) -> None:
        """Load and display all configured providers."""
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

        if not self.config.config.ai or not self.config.config.ai.providers:
            # Show no providers message
            grid.mount(Static(
                "No AI providers configured yet.\n\n"
                "Click 'Add New Provider' to configure your first provider.",
                id="no-providers"
            ))
            return

        # Get default provider
        default_id = self.config.config.ai.default

        # Display each provider
        for provider_id, provider_cfg in self.config.config.ai.providers.items():
            is_default = (provider_id == default_id)
            card = ProviderCard(
                provider_id=provider_id,
                provider_cfg=provider_cfg.dict(),
                is_default=is_default
            )
            if is_default:
                card.add_class("default")
            grid.mount(card)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        button_id = event.button.id

        if button_id == "add-provider-button":
            self.handle_add_provider()
        elif button_id.startswith("set-default-") or button_id.startswith("test-") or button_id.startswith("delete-"):
            # Find the ProviderCard that contains this button
            card = event.button.parent.parent  # Button -> Horizontal -> ProviderCard
            if isinstance(card, ProviderCard):
                provider_id = card.provider_id

                if button_id.startswith("set-default-"):
                    self.handle_set_default(provider_id)
                elif button_id.startswith("test-"):
                    self.handle_test_connection(provider_id)
                elif button_id.startswith("delete-"):
                    self.handle_delete(provider_id)

    def handle_add_provider(self) -> None:
        """Open the configuration wizard to add a new provider."""
        from .ai_config_wizard import AIConfigWizardScreen

        self.app.push_screen(AIConfigWizardScreen(self.config))

    def handle_set_default(self, provider_id: str) -> None:
        """Set a provider as default."""

        try:
            # Load global config
            global_config_path = TitanConfig.GLOBAL_CONFIG
            with open(global_config_path, "rb") as f:
                global_config_data = tomli.load(f)

            # Update default
            global_config_data["ai"]["default"] = provider_id

            # Save to disk
            with open(global_config_path, "wb") as f:
                tomli_w.dump(global_config_data, f)

            # Reload and refresh display
            self.config.load()
            self.load_providers()

            # Update status bar
            self._refresh_status_bar()

            provider_name = self.config.config.ai.providers[provider_id].name
            self.app.notify(f"'{provider_name}' is now the default provider", severity="information")

        except Exception as e:
            self.app.notify(f"Failed to set default: {e}", severity="error")

    def handle_test_connection(self, provider_id: str) -> None:
        """Test connection to a provider."""
        from titan_cli.commands.ai import _test_ai_connection_by_id
        from titan_cli.core.secrets import SecretManager

        # Reload config to get latest
        self.config.load()
        secrets = SecretManager()

        if provider_id not in self.config.config.ai.providers:
            self.app.notify("Provider not found", severity="error")
            return

        provider_cfg = self.config.config.ai.providers[provider_id]

        # Suspend TUI to run test
        with self.app.suspend():
            _test_ai_connection_by_id(provider_id, secrets, self.config.config.ai, provider_cfg)

    def handle_delete(self, provider_id: str) -> None:
        """Delete a provider."""
        import tomli
        import tomli_w
        from titan_cli.core.config import TitanConfig
        from titan_cli.core.secrets import SecretManager

        try:
            # Reload config
            self.config.load()

            if provider_id not in self.config.config.ai.providers:
                self.app.notify("Provider not found", severity="error")
                return

            provider_name = self.config.config.ai.providers[provider_id].name

            # Load global config
            global_config_path = TitanConfig.GLOBAL_CONFIG
            with open(global_config_path, "rb") as f:
                global_config_data = tomli.load(f)

            # Remove provider
            del global_config_data["ai"]["providers"][provider_id]

            # If this was the default, set a new default (first available)
            if global_config_data["ai"].get("default") == provider_id:
                remaining_providers = list(global_config_data["ai"]["providers"].keys())
                if remaining_providers:
                    global_config_data["ai"]["default"] = remaining_providers[0]
                else:
                    global_config_data["ai"]["default"] = None

            # Save to disk
            with open(global_config_path, "wb") as f:
                tomli_w.dump(global_config_data, f)

            # Delete API key from secrets
            secrets = SecretManager()
            try:
                secrets.delete(f"{provider_id}_api_key", scope="user")
            except Exception:
                pass  # Key might not exist

            # Reload and refresh display
            self.config.load()
            self.load_providers()

            # Update status bar
            self._refresh_status_bar()

            self.app.notify(f"Provider '{provider_name}' deleted", severity="information")

        except Exception as e:
            self.app.notify(f"Failed to delete provider: {e}", severity="error")

    def action_back(self) -> None:
        """Go back to main menu."""
        self.app.pop_screen()
