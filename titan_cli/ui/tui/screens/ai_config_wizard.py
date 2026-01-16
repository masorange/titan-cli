"""
AI Configuration Wizard Screen

Step-by-step wizard for configuring AI providers with visual progress tracking.
"""

from textual.app import ComposeResult
from textual.widgets import Static, Button, OptionList, Input
from textual.widgets.option_list import Option
from textual.containers import Container, Horizontal, VerticalScroll
from textual.binding import Binding

from titan_cli.ui.tui.icons import Icons
from titan_cli.ui.tui.widgets import Text, DimText
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


class AIConfigWizardScreen(BaseScreen):
    """
    Wizard screen for AI provider configuration.
    """

    BINDINGS = [
        Binding("escape", "back", "Back"),
    ]

    CSS = """
    AIConfigWizardScreen {
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

    #steps-content {
        height: auto;
    }

    #button-container {
        height: auto;
        padding: 1 2;
        background: $surface-lighten-1;
        border-top: solid $primary;
        align: right middle;
    }

    Button {
        margin: 0 1;
    }

    Button:focus {
        text-style: none;
    }

    #options-list {
        height: auto;
        margin-top: 1;
        margin-bottom: 2;
        border: solid $accent;
    }

    #options-list > .option-list--option {
        padding: 1;
    }

    #options-list > .option-list--option-highlighted {
        padding: 1;
    }

    Input {
        width: 100%;
        margin-top: 1;
        border: solid $accent;
    }

    Input:focus {
        border: solid $primary;
    }
    """

    def __init__(self, config):
        super().__init__(
            config,
            title=f"{Icons.SETTINGS} Configure AI Provider",
            show_back=True
        )
        self.current_step = 0
        self.wizard_data = {}

        # Define all wizard steps
        self.steps = [
            {"id": "type", "title": "Configuration Type"},
            {"id": "base_url", "title": "Base URL"},
            {"id": "provider", "title": "Select Provider"},
            {"id": "api_key", "title": "API Key"},
            {"id": "model", "title": "Select Model"},
            {"id": "name", "title": "Provider Name"},
            {"id": "advanced", "title": "Advanced Options"},
            {"id": "review", "title": "Review & Save"},
        ]

    def compose_content(self) -> ComposeResult:
        """Compose the wizard screen with two panels."""
        with Container(id="wizard-container"):
            with Horizontal():
                # Left panel: Steps
                left_panel = VerticalScroll(id="steps-panel")
                left_panel.border_title = "Configuration Steps"
                with left_panel:
                    with Container(id="steps-content"):
                        for i, step in enumerate(self.steps, 1):
                            status = "in_progress" if i == 1 else "pending"
                            yield StepIndicator(i, step["title"], status=status)

                # Right panel: Content
                right_panel = Container(id="content-panel")
                right_panel.border_title = "Step Configuration"
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

        # Load step content
        content_title = self.query_one("#content-title", Static)
        content_body = self.query_one("#content-body", Container)

        if step["id"] == "type":
            self.load_type_step(content_title, content_body)
        elif step["id"] == "base_url":
            self.load_base_url_step(content_title, content_body)
        elif step["id"] == "provider":
            self.load_provider_step(content_title, content_body)
        elif step["id"] == "api_key":
            self.load_api_key_step(content_title, content_body)
        elif step["id"] == "model":
            self.load_model_step(content_title, content_body)
        elif step["id"] == "name":
            self.load_name_step(content_title, content_body)
        elif step["id"] == "advanced":
            self.load_advanced_step(content_title, content_body)
        elif step["id"] == "review":
            self.load_review_step(content_title, content_body)

    def load_type_step(self, title_widget: Static, body_widget: Container) -> None:
        """Load Configuration Type step."""
        title_widget.update("Select Configuration Type")

        # Clear previous content
        body_widget.remove_children()

        # Add description
        description = Static(
            "Choose the type of AI configuration:\n\n"
            "• Corporate: Use your company's AI endpoint\n"
            "• Individual: Use your personal API key"
        )
        body_widget.mount(description)

        # Add options
        options = OptionList(
            Option("Corporate Configuration", id="corporate"),
            Option("Individual Configuration", id="individual"),
            id="options-list"
        )
        body_widget.mount(options)

        # Focus the options list
        self.call_after_refresh(lambda: options.focus())

    def load_base_url_step(self, title_widget: Static, body_widget: Container) -> None:
        """Load Base URL step (only for corporate)."""
        title_widget.update("Base URL Configuration")
        body_widget.remove_children()

        # Add description
        description = Text(
            "Configure your corporate AI endpoint.\n\n"
            "Enter the base URL for your organization's AI service."
        )
        body_widget.mount(description)

        # Add examples
        examples = DimText(
            "\nExamples:\n"
            "  • https://ai.yourcompany.com\n"
            "  • https://api.internal.corp/ai\n"
            "  • https://llm-gateway.enterprise.local"
        )
        body_widget.mount(examples)

        # Add input field with default value
        default_url = self.wizard_data.get("base_url", "https://")
        input_widget = Input(
            value=default_url,
            placeholder="Enter base URL...",
            id="base-url-input"
        )
        input_widget.styles.margin = (2, 0, 0, 0)
        body_widget.mount(input_widget)

        # Focus the input
        self.call_after_refresh(lambda: input_widget.focus())

    def load_provider_step(self, title_widget: Static, body_widget: Container) -> None:
        """Load Provider Selection step."""
        title_widget.update("Select AI Provider")
        body_widget.remove_children()

        # TODO: Implement provider selection
        description = Static("Provider selection step - Coming soon")
        body_widget.mount(description)

    def load_api_key_step(self, title_widget: Static, body_widget: Container) -> None:
        """Load API Key step."""
        title_widget.update("Enter API Key")
        body_widget.remove_children()

        # TODO: Implement API key input
        description = Static("API Key step - Coming soon")
        body_widget.mount(description)

    def load_model_step(self, title_widget: Static, body_widget: Container) -> None:
        """Load Model Selection step."""
        title_widget.update("Select Model")
        body_widget.remove_children()

        # TODO: Implement model selection
        description = Static("Model selection step - Coming soon")
        body_widget.mount(description)

    def load_name_step(self, title_widget: Static, body_widget: Container) -> None:
        """Load Provider Name step."""
        title_widget.update("Provider Name")
        body_widget.remove_children()

        # TODO: Implement name input
        description = Static("Provider name step - Coming soon")
        body_widget.mount(description)

    def load_advanced_step(self, title_widget: Static, body_widget: Container) -> None:
        """Load Advanced Options step."""
        title_widget.update("Advanced Options")
        body_widget.remove_children()

        # TODO: Implement advanced options
        description = Static("Advanced options step - Coming soon")
        body_widget.mount(description)

    def load_review_step(self, title_widget: Static, body_widget: Container) -> None:
        """Load Review & Save step."""
        title_widget.update("Review Configuration")
        body_widget.remove_children()

        # TODO: Implement review
        description = Static("Review step - Coming soon")
        body_widget.mount(description)

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        """Handle option selection in lists - auto-advance to next step."""
        # Save the selection and move to next step
        self.handle_next()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle Enter key in input fields - auto-advance to next step."""
        self.handle_next()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "next-button":
            self.handle_next()
        elif event.button.id == "back-button":
            self.handle_back()
        elif event.button.id == "cancel-button":
            self.action_back()

    def handle_next(self) -> None:
        """Move to next step."""
        # Validate and save current step data
        if not self.validate_and_save_step():
            return

        # Move to next step
        if self.current_step < len(self.steps) - 1:
            next_step = self.current_step + 1

            # Skip Base URL step if Individual was selected
            if self.steps[next_step]["id"] == "base_url" and self.wizard_data.get("config_type") == "individual":
                next_step += 1

            self.load_step(next_step)

    def validate_and_save_step(self) -> bool:
        """Validate and save data from current step."""
        step = self.steps[self.current_step]

        if step["id"] == "type":
            # Get selected configuration type
            try:
                options_list = self.query_one("#options-list", OptionList)
                if options_list.highlighted is None:
                    self.app.notify("Please select a configuration type", severity="warning")
                    return False

                selected_option = options_list.get_option_at_index(options_list.highlighted)
                self.wizard_data["config_type"] = selected_option.id
                return True
            except Exception:
                self.app.notify("Please select a configuration type", severity="error")
                return False

        elif step["id"] == "base_url":
            # Get base URL from input
            try:
                input_widget = self.query_one("#base-url-input", Input)
                base_url = input_widget.value.strip()

                # Validate URL
                if not base_url:
                    self.app.notify("Please enter a base URL", severity="warning")
                    return False

                if not base_url.startswith(("http://", "https://")):
                    self.app.notify("Base URL must start with http:// or https://", severity="warning")
                    return False

                self.wizard_data["base_url"] = base_url
                return True
            except Exception:
                self.app.notify("Please enter a valid base URL", severity="error")
                return False

        # TODO: Add validation for other steps
        return True

    def handle_back(self) -> None:
        """Move to previous step."""
        if self.current_step > 0:
            prev_step = self.current_step - 1

            # Skip Base URL step if going back and config type is Individual
            if self.steps[prev_step]["id"] == "base_url" and self.wizard_data.get("config_type") == "individual":
                prev_step -= 1

            self.load_step(prev_step)

    def action_back(self) -> None:
        """Go back to AI config menu."""
        self.app.pop_screen()
