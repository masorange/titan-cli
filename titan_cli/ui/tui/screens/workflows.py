"""
Workflows Screen

Screen for listing and executing workflows.
"""

from textual.app import ComposeResult
from textual.widgets import Static, OptionList
from textual.widgets.option_list import Option
from textual.containers import Container
from textual.containers import Horizontal

from .base import BaseScreen


class WorkflowsScreen(BaseScreen):
    """
    Workflows screen for selecting and executing workflows.

    Lists all available workflows and allows the user to:
    - View workflow details
    - Execute workflows
    - Go back to main menu
    """

    BINDINGS = [
        ("escape", "go_back", "Back"),
        ("q", "go_back", "Back"),
    ]

    CSS = """
    WorkflowsScreen {
        align: center middle;
    }

    #workflows-container {
        width: 100%;
        height: auto;
        background: $surface-lighten-1;
    }

    #workflows-title {
        text-align: center;
        color: $primary;
        text-style: bold;
        margin-bottom: 1;
    }

    Horizontal {
        width: 100%;
        height: 1fr;
        padding: 1;
    }

    #left-panel {
        width: 20%;
        border: round $primary;
        border-title-align: center;
    }

    #right-panel {
        width: 80%;
        border: round $primary;
        border-title-align: center;
        background: $surface-lighten-1;
        padding: 0;
    }

    #right-panel OptionList {
        height: 100%;
        width: 100%;
        padding: 1 0;
        margin: 0;
    }

    """

    def compose_content(self) -> ComposeResult:

        self.config.load()
        available_workflows = self.config.workflows.discover()

        """Compose the workflows screen content."""
        with Container(id="workflows-container"):
            yield Static("⚡ Available Workflows", id="workflows-title")

            if not available_workflows:
                yield Static("No workflows found.", id="no-workflows")
            else:
                # Build workflow options
                options = []
                for wf_info in available_workflows:
                    label = f"⚡ {wf_info.name}"
                    description = f"({wf_info.source}) {wf_info.description}"
                    options.append(
                        Option(f"{label}\n  [dim]{description}[/dim]", id=wf_info.name)
                    )

                with Horizontal():
                    left_panel = Container(id="left-panel")
                    left_panel.border_title = "Plugins"
                    with left_panel:
                        yield Static("Hola 1 - Left")

                    right_panel = Container(id="right-panel")
                    right_panel.border_title = "Workflows"
                    with right_panel:
                        yield OptionList(*options)

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        """Handle workflow selection."""
        workflow_name = event.option.id

        if workflow_name == "back":
            self.action_go_back()
        else:
            self.execute_workflow(workflow_name)

    def execute_workflow(self, workflow_name: str) -> None:
        """
        Execute a workflow.

        Args:
            workflow_name: Name of the workflow to execute
        """
        # TODO: Implement workflow execution
        # For now, just show a notification
        self.app.notify(f"Executing workflow: {workflow_name} - Coming soon!")

    def action_go_back(self) -> None:
        """Go back to main menu."""
        self.app.pop_screen()
