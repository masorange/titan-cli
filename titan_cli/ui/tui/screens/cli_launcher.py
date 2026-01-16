"""
CLI Launcher Screen

Screen for launching external CLI tools (Claude, Gemini, etc.)
"""

from textual.app import ComposeResult
from textual.widgets import Static, OptionList
from textual.widgets.option_list import Option
from textual.containers import Container
from textual.binding import Binding

from titan_cli.external_cli.launcher import CLILauncher
from titan_cli.external_cli.configs import CLI_REGISTRY
from .base import BaseScreen


class CLILauncherScreen(BaseScreen):
    """
    Screen for selecting and launching external CLI tools.
    """

    BINDINGS = [
        Binding("escape", "back", "Back"),
    ]

    CSS = """
    CLILauncherScreen {
        align: center middle;
    }

    #launcher-container {
        width: 70%;
        height: auto;
        background: $surface-lighten-1;
        border: solid $primary;
        margin: 1;
        padding: 2;
    }

    #launcher-title {
        text-align: center;
        color: $primary;
        text-style: bold;
        margin-bottom: 2;
    }

    .info-text {
        color: $text-muted;
        text-align: center;
        margin-bottom: 2;
    }

    #cli-options {
        height: auto;
        border: none;
        background: $surface-lighten-1;
    }

    #cli-options > .option-list--option {
        padding: 1;
    }

    #cli-options > .option-list--option-highlighted {
        padding: 1;
    }
    """

    def __init__(self, config):
        super().__init__(config)
        self.available_clis = self._get_available_clis()

    def _get_available_clis(self) -> dict:
        """Get list of available CLI tools."""
        available = {}
        for cli_name, config in CLI_REGISTRY.items():
            launcher = CLILauncher(
                cli_name,
                install_instructions=config.get("install_instructions"),
                prompt_flag=config.get("prompt_flag")
            )
            if launcher.is_available():
                available[cli_name] = {
                    "launcher": launcher,
                    "display_name": config.get("display_name", cli_name)
                }
        return available

    def compose_content(self) -> ComposeResult:
        """Compose the CLI launcher screen."""
        with Container(id="launcher-container"):
            yield Static("🚀 Launch External CLI", id="launcher-title")

            if not self.available_clis:
                yield Static(
                    "⚠️  No external CLI tools found.\n\n"
                    "Install Claude CLI or Gemini CLI to use this feature.\n\n"
                    "Press ESC to go back.",
                    classes="info-text"
                )
            else:
                yield Static(
                    "Select a CLI tool to launch:",
                    classes="info-text"
                )

                options = [
                    Option(info["display_name"], id=cli_name)
                    for cli_name, info in self.available_clis.items()
                ]
                yield OptionList(*options, id="cli-options")

    def on_mount(self) -> None:
        """Focus the CLI list when mounted."""
        if self.available_clis:
            self.query_one("#cli-options").focus()

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        """Handle CLI selection and launch immediately."""
        cli_name = event.option.id

        if cli_name not in self.available_clis:
            self.app.notify("Invalid CLI selection", severity="error")
            return

        # Get launcher
        launcher = self.available_clis[cli_name]["launcher"]
        display_name = self.available_clis[cli_name]["display_name"]

        # Notify user
        self.app.notify(f"Launching {display_name}...")

        # Suspend TUI and launch CLI
        with self.app.suspend():
            exit_code = launcher.launch(prompt=None, cwd=".")

        # Show result
        if exit_code == 0:
            self.app.notify(f"{display_name} exited successfully", severity="information")
        else:
            self.app.notify(
                f"{display_name} exited with code {exit_code}",
                severity="warning"
            )

        # Go back to main menu
        self.action_back()

    def action_back(self) -> None:
        """Go back to main menu."""
        self.app.pop_screen()
