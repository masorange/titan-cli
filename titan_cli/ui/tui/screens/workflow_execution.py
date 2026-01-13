"""
Workflow Execution Screen

Screen for executing workflows and displaying progress in real-time.
"""

from textual.app import ComposeResult
from textual.widgets import Static
from textual.containers import Container

from .base import BaseScreen


class WorkflowExecutionScreen(BaseScreen):
    """
    Screen for executing a workflow with real-time progress display.

    The internal structure (progress tracking, output handling, etc.)
    will be implemented separately.
    """

    BINDINGS = [
        ("escape", "cancel_execution", "Cancel"),
        ("q", "cancel_execution", "Cancel"),
    ]

    CSS = """
    WorkflowExecutionScreen {
        align: center middle;
    }

    #execution-container {
        width: 100%;
        height: 1fr;
        background: $surface-lighten-1;
        padding: 2;
    }
    """

    def __init__(self, config, workflow_name: str, **kwargs):
        super().__init__(
            config,
            title=f"⚡ Executing: {workflow_name}",
            show_back=False,
            **kwargs
        )
        self.workflow_name = workflow_name

    def compose_content(self) -> ComposeResult:
        """Compose the workflow execution screen."""
        with Container(id="execution-container"):
            yield Static(
                f"Workflow: {self.workflow_name}\n\n"
                "Execution UI will be implemented here...",
                id="placeholder"
            )

    def action_cancel_execution(self) -> None:
        """Cancel workflow execution and go back."""
        self.app.pop_screen()
