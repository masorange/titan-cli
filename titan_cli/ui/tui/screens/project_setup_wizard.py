"""
Project Setup Wizard Screen

Wizard for configuring a new Titan project in the current directory.
"""

from textual.app import ComposeResult
from textual.widgets import Static, OptionList, Input
from textual.widgets.option_list import Option
from textual.containers import Container, Horizontal, VerticalScroll
from textual.binding import Binding
from pathlib import Path

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


class ProjectSetupWizardScreen(BaseScreen):
    """
    Project setup wizard for configuring Titan in a project.

    This wizard runs when Titan is launched from a directory that doesn't
    have a .titan/config.toml file.
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
    ]

    CSS = """
    ProjectSetupWizardScreen {
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

    def __init__(self, config, project_path: Path):
        super().__init__(
            config,
            title=f"{Icons.SETTINGS} Project Setup",
            show_back=False
        )
        self.project_path = project_path
        self.current_step = 0
        self.wizard_data = {}

        # Detect if it's a git repository
        self.is_git_repo = (project_path / ".git").exists()

        # Define all wizard steps
        self.steps = [
            {"id": "welcome", "title": "Welcome"},
            {"id": "project_name", "title": "Project Name"},
            {"id": "select_plugins", "title": "Select Plugins"},
            {"id": "complete", "title": "Complete"},
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
                right_panel.border_title = "Project Configuration"
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
        elif step["id"] == "project_name":
            self.load_project_name_step(content_title, content_body)
        elif step["id"] == "select_plugins":
            self.load_select_plugins_step(content_title, content_body)
        elif step["id"] == "complete":
            self.load_complete_step(content_title, content_body)

    def load_welcome_step(self, title_widget: Static, body_widget: Container) -> None:
        """Load Welcome step."""
        title_widget.update("Configure This Project")

        # Clear previous content
        body_widget.remove_children()

        # Add welcome message
        project_dir = self.project_path.name
        welcome_text = Text(
            f"Welcome to project setup for '{project_dir}'!\n\n"
            "This wizard will help you configure Titan for this project.\n\n"
        )
        body_widget.mount(welcome_text)

        # Detect project type
        project_type_info = BoldText("Detected Project Type:\n")
        body_widget.mount(project_type_info)

        if self.is_git_repo:
            git_info = Text(
                "  ✓ Git Repository\n\n"
                "Titan can help you with:\n"
                "  • AI-powered commit messages\n"
                "  • Branch management\n"
                "  • GitHub integration (PRs, issues)\n"
                "  • Jira integration (issue tracking)\n"
            )
            body_widget.mount(git_info)
        else:
            no_git_info = DimText(
                "  ✗ Not a Git repository\n\n"
                "You can still use Titan for workflows and AI features.\n"
            )
            body_widget.mount(no_git_info)

        # Add next steps
        next_steps = Text(
            "\nIn the next steps, you'll:\n"
            "  1. Name your project\n"
            "  2. Select plugins to enable\n"
        )
        body_widget.mount(next_steps)

    def load_project_name_step(self, title_widget: Static, body_widget: Container) -> None:
        """Load Project Name step."""
        title_widget.update("Project Name")
        body_widget.remove_children()

        # Add description
        description = Text(
            "Enter a name for this project.\n\n"
            "This helps identify the project in Titan's configuration."
        )
        body_widget.mount(description)

        # Default to directory name
        default_name = self.wizard_data.get("project_name", self.project_path.name)

        # Add example
        example = DimText(
            f"\nExamples:\n"
            f"  • {self.project_path.name}\n"
            f"  • my-awesome-project\n"
            f"  • company-backend-api"
        )
        body_widget.mount(example)

        # Add input field
        input_widget = Input(
            value=default_name,
            placeholder="Enter project name...",
            id="project-name-input"
        )
        input_widget.styles.margin = (2, 0, 0, 0)
        body_widget.mount(input_widget)

        # Focus the input
        self.call_after_refresh(lambda: input_widget.focus())

    def load_select_plugins_step(self, title_widget: Static, body_widget: Container) -> None:
        """Load Select Plugins step."""
        title_widget.update("Select Plugins")
        body_widget.remove_children()

        # Add description
        description = Text(
            "Select which plugins to enable for this project.\n\n"
            "You can change these settings later from the main menu."
        )
        body_widget.mount(description)

        # Get available plugins
        # Check which plugins are installed globally
        installed_plugins = self.config.registry.list_discovered()

        if not installed_plugins:
            no_plugins = DimText(
                "\nNo plugins are currently installed.\n"
                "You can install plugins later from the main menu:\n"
                "  Main Menu → Plugin Management → Install a new Plugin"
            )
            body_widget.mount(no_plugins)
            return

        # Build plugin options
        # Automatically suggest enabling Git plugin if it's a git repo
        auto_enable = []
        if self.is_git_repo and "git" in installed_plugins:
            auto_enable.append("git")

        plugin_info = DimText(
            f"\nAvailable plugins ({len(installed_plugins)} installed):\n"
        )
        body_widget.mount(plugin_info)

        # Create a checklist-style option list
        # For now, we'll use OptionList and track selections manually
        # In the future, we could create a custom widget for checkboxes
        options = []
        for plugin_name in installed_plugins:
            label = f"☐ {plugin_name}"
            if plugin_name in auto_enable:
                label = f"☑ {plugin_name} (recommended)"
            options.append(Option(label, id=plugin_name))

        if options:
            options_list = OptionList(*options, id="options-list")
            body_widget.mount(options_list)

            # Store auto-enabled plugins
            self.wizard_data["auto_enabled_plugins"] = auto_enable

            # Add instructions
            instructions = DimText(
                "\n\nNote: Select a plugin and press Enter to toggle it.\n"
                "You can select multiple plugins."
            )
            body_widget.mount(instructions)

            # Focus the options list
            self.call_after_refresh(lambda: options_list.focus())

    def load_complete_step(self, title_widget: Static, body_widget: Container) -> None:
        """Load Setup Complete step."""
        title_widget.update("Project Configured!")
        body_widget.remove_children()

        # Add completion message
        project_name = self.wizard_data.get("project_name", self.project_path.name)
        completion_text = BoldText(
            f"Project '{project_name}' has been configured successfully!\n"
        )
        body_widget.mount(completion_text)

        # Show selected plugins
        enabled_plugins = self.wizard_data.get("enabled_plugins", [])
        if enabled_plugins:
            plugins_text = Text(
                f"\n\nEnabled Plugins ({len(enabled_plugins)}):\n"
            )
            body_widget.mount(plugins_text)

            for plugin in enabled_plugins:
                plugin_item = DimText(f"  • {plugin}")
                body_widget.mount(plugin_item)
        else:
            no_plugins_text = DimText(
                "\n\nNo plugins were enabled.\n"
                "You can enable them later from the main menu."
            )
            body_widget.mount(no_plugins_text)

        # Add next steps
        next_steps = Text(
            "\n\nYou can now:\n"
            "  • Run workflows\n"
            "  • Configure plugin settings\n"
            "  • Install additional plugins\n"
        )
        body_widget.mount(next_steps)

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        """Handle option selection in plugin list - toggle selection."""
        step = self.steps[self.current_step]

        # Only toggle for select_plugins step
        if step["id"] == "select_plugins":
            # Toggle the plugin selection
            plugin_id = event.option.id
            enabled_plugins = self.wizard_data.get("enabled_plugins", [])

            if plugin_id in enabled_plugins:
                enabled_plugins.remove(plugin_id)
                # Update label to unchecked
                new_label = f"☐ {plugin_id}"
            else:
                enabled_plugins.append(plugin_id)
                # Update label to checked
                new_label = f"☑ {plugin_id}"

            self.wizard_data["enabled_plugins"] = enabled_plugins

            # Update the option label
            options_list = self.query_one("#options-list", OptionList)
            option_index = event.option_index
            # Remove and re-add option with new label
            options_list.remove_option_at_index(option_index)
            options_list.add_option(Option(new_label, id=plugin_id), index=option_index)
            # Re-highlight the option
            options_list.highlighted = option_index

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

        # Move to next step
        if self.current_step < len(self.steps) - 1:
            self.load_step(self.current_step + 1)

    def validate_and_save_step(self) -> bool:
        """Validate and save data from current step."""
        step = self.steps[self.current_step]

        if step["id"] == "welcome":
            # No validation needed for welcome step
            return True

        elif step["id"] == "project_name":
            # Get project name from input
            try:
                input_widget = self.query_one("#project-name-input", Input)
                project_name = input_widget.value.strip()

                # Validate project name
                if not project_name:
                    self.app.notify("Please enter a project name", severity="warning")
                    return False

                self.wizard_data["project_name"] = project_name
                return True
            except Exception:
                self.app.notify("Please enter a valid project name", severity="error")
                return False

        elif step["id"] == "select_plugins":
            # Get enabled plugins (already saved during selection)
            # Initialize with auto-enabled if not already set
            if "enabled_plugins" not in self.wizard_data:
                self.wizard_data["enabled_plugins"] = self.wizard_data.get("auto_enabled_plugins", [])
            return True

        return True

    def handle_back(self) -> None:
        """Move to previous step."""
        if self.current_step > 0:
            self.load_step(self.current_step - 1)

    def complete_setup(self) -> None:
        """Complete the project setup."""
        import tomli_w

        try:
            # Create .titan directory in project
            titan_dir = self.project_path / ".titan"
            titan_dir.mkdir(exist_ok=True)

            # Create project config
            project_config_path = titan_dir / "config.toml"

            project_name = self.wizard_data.get("project_name", self.project_path.name)
            enabled_plugins = self.wizard_data.get("enabled_plugins", [])

            # Build project config structure
            project_config_data = {
                "project": {
                    "name": project_name,
                },
                "plugins": {}
            }

            # Add enabled plugins
            for plugin_name in enabled_plugins:
                project_config_data["plugins"][plugin_name] = {
                    "enabled": True
                }

            # Save project config
            with open(project_config_path, "wb") as f:
                tomli_w.dump(project_config_data, f)

            self.app.notify(f"Project '{project_name}' configured successfully!", severity="information")

            # Close wizard - the callback will handle navigation
            self.dismiss()

        except Exception as e:
            self.app.notify(f"Failed to complete project setup: {e}", severity="error")

    def action_cancel(self) -> None:
        """Cancel the setup wizard."""
        self.app.exit(message="Project setup cancelled. Run Titan again to configure this project.")
