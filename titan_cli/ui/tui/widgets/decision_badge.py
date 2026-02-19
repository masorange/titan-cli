"""
DecisionBadge Widget

Shows a user decision result after a prompt is answered.
Used to replace interactive widgets (PromptChoice, PromptInput, etc.) once
the user has made a choice, providing a clear visual summary of what was decided.
"""

from textual.widget import Widget
from textual.widgets import Static


class DecisionBadge(Widget):
    """
    Shows a user decision result with a left-border indicator and label.

    Intended to replace interactive prompt widgets after the user responds,
    giving a clean, scannable record of what was decided at each step.

    Args:
        label: Text describing the decision taken (e.g. "✓ Yes", "AI Review & Fix")
        variant: Visual style — "default", "success", "warning", "error"
    """

    DEFAULT_CSS = """
    DecisionBadge {
        width: auto;
        height: auto;
        padding: 0 2;
        margin: 0 0 1 0;
        border-left: thick $accent;
        color: $text-muted;
    }

    DecisionBadge.success {
        border-left: thick $success;
        color: $success;
    }

    DecisionBadge.warning {
        border-left: thick $warning;
        color: $warning;
    }

    DecisionBadge.error {
        border-left: thick $error;
        color: $error;
    }
    """

    def __init__(self, label: str, variant: str = "default", **kwargs):
        super().__init__(**kwargs)
        self.label = label
        if variant != "default":
            self.add_class(variant)

    def compose(self):
        yield Static(self.label)
