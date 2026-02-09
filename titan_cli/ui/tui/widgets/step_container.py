"""
Step Container Widget

A container that groups all output from a workflow step, with a titled border
that changes color based on the step result (success, skip, error).

Now uses PanelContainer as base for consistent theming.
"""
from .panel_container import PanelContainer


class StepContainer(PanelContainer):
    """
    Container for step output with colored border and title.

    The border color changes based on step result:
    - Running: info (cyan/accent)
    - Success: success (green)
    - Skip: warning (yellow)
    - Error: error (red)

    Inherits from PanelContainer for consistent styling.
    """

    DEFAULT_CSS = """
    StepContainer.running {
        border: round $accent;
    }

    StepContainer.skip {
        border: round $warning;
    }
    """

    def __init__(self, step_name: str, **kwargs):
        """
        Initialize step container.

        Args:
            step_name: Name of the step (shown in border title)
        """
        # Initialize with 'info' variant (cyan border for running state)
        super().__init__(variant="info", title=step_name, **kwargs)
        self.add_class("running")

    def set_result(self, result_type: str):
        """
        Update the border color based on step result.

        Args:
            result_type: One of 'success', 'skip', 'error'
        """
        # Remove running class
        self.remove_class("running")

        # Map step results to PanelContainer variants
        if result_type == "success":
            self.set_variant("success")
        elif result_type == "skip":
            # Add skip class for yellow border
            self.add_class("skip")
        elif result_type == "error":
            self.set_variant("error")
        else:
            # Default to running state
            self.set_variant("info")
            self.add_class("running")
