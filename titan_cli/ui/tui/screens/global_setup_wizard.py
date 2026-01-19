"""
Global Setup Wizard Screen

First-time installation wizard for configuring Titan globally.
"""

from textual.app import ComposeResult
from textual.widgets import Static
from textual.containers import Container, Horizontal, VerticalScroll
from textual.binding import Binding

from titan_cli.ui.tui.icons import Icons
from titan_cli.ui.tui.widgets import Text, DimText, Button, BoldText
from .base import BaseScreen


class StepIndicator(Static):
    """Widget showing a single step with status indicator."""

    def __init__(self, step_number: int, title: str, status: str = "pending"):
        self.step_number = step_number
        self.title = title
        self.status = status
        super().__init__()

    def render(self) -> str:
        """Render the step with appropriate icon."""
        if self.status == "completed":
            icon = Icons.SUCCESS
            style = "dim"
        elif self.status == "in_progress":
            icon = Icons.RUNNING
            style = "bold cyan"
        else:  # pending
            icon = Icons.PENDING
            style = "dim"

        return f"[{style}]{icon} {self.step_number}. {self.title}[/{style}]"


class GlobalSetupWizardScreen(BaseScreen):
    """
    First-time setup wizard for Titan.

    This wizard runs when Titan is launched for the first time
    and ~/.titan/config.toml doesn't exist.
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
    ]

    CSS = """
    GlobalSetupWizardScreen {
        align: center middle;
    }

    #wizard-container {
        width: 100%;
        height: 1fr;
        background: $surface-lighten-1;
        padding: 0 2 1 2;
    }

    #steps-panel {
        width: 20%;
        height: 100%;
        border: round $primary;
        border-title-align: center;
        background: $surface-lighten-1;
        padding: 0;
    }

    #steps-content {
        padding: 1;
    }

    StepIndicator {
        height: auto;
        margin-bottom: 1;
    }

    #content-panel {
        width: 80%;
        height: 100%;
        border: round $primary;
        border-title-align: center;
        background: $surface-lighten-1;
        padding: 0;
        layout: vertical;
    }

    #content-scroll {
        height: 1fr;
    }

    #content-area {
        padding: 1;
        height: auto;
    }

    #content-title {
        color: $accent;
        text-style: bold;
        margin-bottom: 2;
        height: auto;
    }

    #content-body {
        height: auto;
        margin-bottom: 2;
    }

    #button-container {
        height: auto;
        padding: 1 2;
        background: $surface-lighten-1;
        border-top: solid $primary;
        align: right middle;
    }
    """

    def __init__(self, config):
        super().__init__(
            config,
            title=f"{Icons.SETTINGS} Titan Setup Wizard",
            show_back=False
        )
        self.current_step = 0
        self.wizard_data = {}

        # Define all wizard steps
        self.steps = [
            {"id": "welcome", "title": "Welcome"},
            {"id": "complete", "title": "Setup Complete"},
        ]

    def compose_content(self) -> ComposeResult:
        """Compose the wizard screen with two panels."""
        with Container(id="wizard-container"):
            with Horizontal():
                # Left panel: Steps
                left_panel = VerticalScroll(id="steps-panel")
                left_panel.border_title = "Setup Steps"
                with left_panel:
                    with Container(id="steps-content"):
                        for i, step in enumerate(self.steps, 1):
                            status = "in_progress" if i == 1 else "pending"
                            yield StepIndicator(i, step["title"], status=status)

                # Right panel: Content
                right_panel = Container(id="content-panel")
                right_panel.border_title = "Setup Configuration"
                with right_panel:
                    with VerticalScroll(id="content-scroll"):
                        with Container(id="content-area"):
                            yield Static("", id="content-title")
                            yield Container(id="content-body")

                    # Bottom buttons
                    with Horizontal(id="button-container"):
                        yield Button("Back", variant="default", id="back-button", disabled=True)
                        yield Button("Next", variant="primary", id="next-button")
                        yield Button("Cancel", variant="default", id="cancel-button")

    def on_mount(self) -> None:
        """Load the first step when mounted."""
        self.load_step(0)

    def load_step(self, step_index: int) -> None:
        """Load content for the given step."""
        self.current_step = step_index
        step = self.steps[step_index]

        # Update step indicators
        for i, indicator in enumerate(self.query(StepIndicator)):
            if i < step_index:
                indicator.status = "completed"
            elif i == step_index:
                indicator.status = "in_progress"
            else:
                indicator.status = "pending"
            indicator.refresh()

        # Update buttons
        back_button = self.query_one("#back-button", Button)
        back_button.disabled = (step_index == 0)

        # Change Next button label based on step
        next_button = self.query_one("#next-button", Button)
        if step_index == len(self.steps) - 1:
            next_button.label = "Finish"
        else:
            next_button.label = "Next"

        # Load step content
        content_title = self.query_one("#content-title", Static)
        content_body = self.query_one("#content-body", Container)

        if step["id"] == "welcome":
            self.load_welcome_step(content_title, content_body)
        elif step["id"] == "complete":
            self.load_complete_step(content_title, content_body)

    def load_welcome_step(self, title_widget: Static, body_widget: Container) -> None:
        """Load Welcome step."""
        title_widget.update("Welcome to Titan CLI!")

        # Clear previous content
        body_widget.remove_children()

        # Add welcome message
        welcome_text = Text(
            "Thank you for installing Titan CLI!\n\n"
            "Titan is a powerful development tools orchestrator that helps you manage Git, GitHub, "
            "Jira, and other services with AI-powered workflows.\n\n"
            "This wizard will help you configure Titan for first-time use."
        )
        body_widget.mount(welcome_text)

        # Add features info
        features = DimText(
            "\n\nKey Features:\n"
            "  • AI-powered commit messages and PR descriptions\n"
            "  • Automated workflows for common tasks\n"
            "  • Seamless integration with Git, GitHub, and Jira\n"
            "  • Extensible plugin system\n"
            "  • Modern terminal UI"
        )
        body_widget.mount(features)

        # Add next steps
        next_steps = Text(
            "\n\nNext, you'll configure your AI provider (Claude or Gemini).\n"
            "This is required to use Titan's AI-powered features."
        )
        body_widget.mount(next_steps)

    def load_complete_step(self, title_widget: Static, body_widget: Container) -> None:
        """Load Setup Complete step."""
        title_widget.update("Setup Complete!")
        body_widget.remove_children()

        # Add completion message
        completion_text = BoldText(
            "Congratulations! Titan has been configured successfully.\n"
        )
        body_widget.mount(completion_text)

        # Add next steps
        next_steps = Text(
            "\n\nWhat's Next?\n\n"
            "When you run Titan from a project directory, you'll be prompted to configure "
            "that specific project.\n\n"
            "For now, Titan is ready to use!"
        )
        body_widget.mount(next_steps)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "next-button":
            self.handle_next()
        elif event.button.id == "back-button":
            self.handle_back()
        elif event.button.id == "cancel-button":
            self.action_cancel()

    def handle_next(self) -> None:
        """Move to next step or complete setup."""
        # Validate and save current step data
        if not self.validate_and_save_step():
            return

        # If on last step, complete setup
        if self.current_step == len(self.steps) - 1:
            self.complete_setup()
            return

        # If on welcome step, launch AI wizard before going to complete
        if self.steps[self.current_step]["id"] == "welcome":
            # Launch AI configuration wizard
            from .ai_config_wizard import AIConfigWizardScreen

            def on_ai_wizard_complete(_=None):
                """Callback when AI wizard is dismissed."""
                # Move to complete step after AI wizard completes
                self.load_step(self.current_step + 1)

            self.app.push_screen(AIConfigWizardScreen(self.config), on_ai_wizard_complete)
            return

        # Move to next step
        if self.current_step < len(self.steps) - 1:
            self.load_step(self.current_step + 1)

    def validate_and_save_step(self) -> bool:
        """Validate and save data from current step."""
        step = self.steps[self.current_step]

        if step["id"] == "welcome":
            # No validation needed for welcome step
            return True

        # No other validation needed
        return True

    def handle_back(self) -> None:
        """Move to previous step."""
        if self.current_step > 0:
            self.load_step(self.current_step - 1)

    def complete_setup(self) -> None:
        """Complete the global setup."""
        import tomli_w
        from titan_cli.core.config import TitanConfig

        try:
            # Create ~/.titan directory
            global_config_path = TitanConfig.GLOBAL_CONFIG
            global_config_path.parent.mkdir(parents=True, exist_ok=True)

            # Create minimal global config
            global_config_data = {
                "version": "1.0",
                # AI config will be added by the AI wizard if user chose to configure
                # Plugins will be added when user enables them in projects
            }

            # Save global config
            with open(global_config_path, "wb") as f:
                tomli_w.dump(global_config_data, f)

            self.app.notify("Global setup completed successfully!", severity="information")

            # Close wizard - the callback will handle navigation
            self.dismiss()

        except Exception as e:
            self.app.notify(f"Failed to complete setup: {e}", severity="error")

    def action_cancel(self) -> None:
        """Cancel the setup wizard."""
        self.app.exit(message="Setup cancelled. Titan requires initial configuration to run.")
