"""
AI Configuration Screen

Screen for configuring AI providers (Anthropic, OpenAI, Gemini)
"""

from textual.app import ComposeResult
from textual.widgets import Static, OptionList
from textual.widgets.option_list import Option
from textual.containers import Container
from textual.binding import Binding

from titan_cli.ui.tui.icons import Icons
from .base import BaseScreen


class AIConfigScreen(BaseScreen):
    """
    Screen for AI provider configuration and management.
    """

    def __init__(self, config):
        super().__init__(
            config,
            title=f"{Icons.SETTINGS} AI Configuration",
            show_back=True
        )

    BINDINGS = [
        Binding("escape", "back", "Back"),
    ]

    CSS = """
    AIConfigScreen {
        align: center middle;
    }

    #ai-config-container {
        width: 70%;
        height: auto;
        background: $surface-lighten-1;
        border: solid $primary;
        padding: 1 0;
    }

    .info-text {
        color: $text-muted;
        text-align: center;
        margin-bottom: 2;
    }

    #ai-options {
        height: auto;
        border: none;
        background: $surface-lighten-1;
    }

    #ai-options > .option-list--option {
        padding: 1;
    }

    #ai-options > .option-list--option-highlighted {
        padding: 1;
    }
    """

    def compose_content(self) -> ComposeResult:
        """Compose the AI configuration screen."""
        with Container(id="ai-config-container"):

            yield Static(
                "Select an option:",
                classes="info-text"
            )

            options = [
                Option(f"{Icons.SETTINGS} Configure AI Provider", id="configure"),
                Option(f"{Icons.PLUGIN} Test AI Connection", id="test"),
                Option(f"{Icons.FILE} List AI Providers", id="list"),
                Option(f"{Icons.STAR} Set Default Provider", id="set_default"),
            ]
            yield OptionList(*options, id="ai-options")

    def on_mount(self) -> None:
        """Focus the options list when mounted."""
        self.query_one("#ai-options").focus()

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        """Handle option selection."""
        action = event.option.id

        if action == "configure":
            self.handle_configure()
        elif action == "test":
            self.handle_test()
        elif action == "list":
            self.handle_list()
        elif action == "set_default":
            self.handle_set_default()

    def handle_configure(self) -> None:
        """Handle Configure AI Provider action."""
        from .ai_config_wizard import AIConfigWizardScreen

        self.app.push_screen(AIConfigWizardScreen(self.config))

    def handle_test(self) -> None:
        """Handle Test AI Connection action."""
        from titan_cli.commands.ai import _test_ai_connection_by_id
        from titan_cli.core.secrets import SecretManager
        from titan_cli.messages import msg

        # Reload config to get latest
        self.config.load()
        secrets = SecretManager()

        if not self.config.config.ai or not self.config.config.ai.providers:
            self.app.notify(msg.AI.PROVIDER_NOT_CONFIGURED, severity="error")
            return

        # Get default provider ID
        default_id = self.config.config.ai.default_provider
        if not default_id:
            self.app.notify("No default AI provider set", severity="error")
            return

        # Suspend TUI to run test
        with self.app.suspend():
            _test_ai_connection_by_id(default_id, self.config, secrets)

    def handle_list(self) -> None:
        """Handle List AI Providers action."""
        from titan_cli.commands.ai import list_providers

        # Suspend TUI to show list
        with self.app.suspend():
            list_providers()

    def handle_set_default(self) -> None:
        """Handle Set Default Provider action."""
        from titan_cli.commands.ai import set_default_provider

        # Suspend TUI to run interactive selection
        with self.app.suspend():
            set_default_provider()

        self.app.notify("Default provider updated", severity="information")

    def action_back(self) -> None:
        """Go back to main menu."""
        self.app.pop_screen()
