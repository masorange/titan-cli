"""
Step Container Widget

A container that groups all output from a workflow step, with a titled border
that changes color based on the step result (success, skip, error).
"""
from textual.containers import VerticalScroll


class StepContainer(VerticalScroll):
    """
    Container for step output with colored border and title.

    The border color changes based on step result:
    - Running: cyan (default)
    - Success: green
    - Skip: yellow
    - Error: red
    """

    DEFAULT_CSS = """
    StepContainer {
        width: 100%;
        height: auto;
        border: round $accent;
        padding: 1 2;
        margin: 1 0;
    }

    StepContainer.running {
        border: round $accent;
    }

    StepContainer.success {
        border: round $success;
    }

    StepContainer.skip {
        border: round $warning;
    }

    StepContainer.error {
        border: round $error;
    }
    """

    def __init__(self, step_name: str, **kwargs):
        super().__init__(**kwargs)
        self.border_title = step_name
        self.add_class("running")

    def set_result(self, result_type: str):
        """
        Update the border color based on step result.

        Args:
            result_type: One of 'success', 'skip', 'error'
        """
        # Remove all result classes
        self.remove_class("running", "success", "skip", "error")

        # Add the new result class
        if result_type in ["success", "skip", "error"]:
            self.add_class(result_type)
        else:
            self.add_class("running")
