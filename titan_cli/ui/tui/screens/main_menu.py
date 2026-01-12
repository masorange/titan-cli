"""
Main Menu Screen

The primary navigation screen for Titan TUI.
"""
from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Static, OptionList
from textual.widgets.option_list import Option
from textual.containers import Container

from titan_cli.core.config import TitanConfig
from titan_cli.ui.tui.widgets.status_bar import StatusBarWidget


class MainMenuScreen(Screen):
    """
    Main menu screen with navigation options.

    Displays the primary actions available in Titan:
    - Launch External CLI
    - Project Management
    - Workflows
    - Plugin Management
    - AI Configuration
    - Switch Project
    - Exit
    """

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("escape", "quit", "Quit"),
    ]

    CSS = """
    MainMenuScreen {
        align: center middle;
    }

    #menu-container {
        width: 100%;
        height: auto;
        background: $surface-lighten-1;
    }

    #menu-title {
        text-align: center;
        color: $primary;
        text-style: bold;
        margin-bottom: 1;
    }

    OptionList {
        height: auto;
        border: none;
    }

    OptionList > .option-list--option {
        padding: 1 2;
    }

    OptionList > .option-list--option-highlighted {
        background: $primary;
    }
    """

    def __init__(self, config: TitanConfig, **kwargs):
        """
        Initialize the main menu screen.

        Args:
            config: TitanConfig instance
        """
        super().__init__(**kwargs)
        self.config = config

    def compose(self) -> ComposeResult:
        """Compose the main menu."""
        with Container(id="menu-container"):
            yield Static("🚀 TITAN CLI - Main Menu", id="menu-title")

            # Build menu options
            options = [
                Option("🚀 Launch External CLI", id="cli"),
                Option("📂 Project Management", id="projects"),
            ]

            # Only show Workflows if there are enabled plugins
            installed_plugins = self.config.registry.list_installed()
            enabled_plugins = [p for p in installed_plugins if self.config.is_plugin_enabled(p)]
            if enabled_plugins:
                options.append(Option("⚡ Workflows", id="run_workflow"))

            options.extend([
                Option("🔌 Plugin Management", id="plugin_management"),
                Option("⚙️  AI Configuration", id="ai_config"),
                Option("🔄 Switch Project", id="switch_project"),
                Option("❌ Exit", id="exit"),
            ])

            yield OptionList(*options)
            yield StatusBarWidget(id="status-bar")

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        """Handle menu option selection."""
        action = event.option.id

        if action == "exit":
            self.app.exit()
        elif action == "cli":
            self.handle_cli_action()
        elif action == "projects":
            self.handle_projects_action()
        elif action == "run_workflow":
            self.handle_workflow_action()
        elif action == "plugin_management":
            self.handle_plugin_management_action()
        elif action == "ai_config":
            self.handle_ai_config_action()
        elif action == "switch_project":
            self.handle_switch_project_action()

    def handle_cli_action(self) -> None:
        """Handle Launch External CLI action."""
        self.app.notify("CLI launcher - Coming soon!")

    def handle_projects_action(self) -> None:
        """Handle Project Management action."""
        self.app.notify("Project management - Coming soon!")

    def handle_workflow_action(self) -> None:
        """Handle Workflows action."""
        from .workflows import WorkflowsScreen
        self.app.push_screen(WorkflowsScreen(self.config))

    def handle_plugin_management_action(self) -> None:
        """Handle Plugin Management action."""
        self.app.notify("Plugin management - Coming soon!")

    def handle_ai_config_action(self) -> None:
        """Handle AI Configuration action."""
        self.app.notify("AI configuration - Coming soon!")

    def handle_switch_project_action(self) -> None:
        """Handle Switch Project action."""
        self.app.notify("Switch project - Coming soon!")

    def action_quit(self) -> None:
        """Quit the application."""
        self.app.exit()
