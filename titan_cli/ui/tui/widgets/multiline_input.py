"""
MultilineInput Widget

Custom TextArea that handles Enter for submission and Shift+Enter for new lines.
"""

from textual.widget import Widget
from textual.widgets import TextArea
from textual.message import Message


class MultilineInput(TextArea):
    """Custom TextArea that handles Ctrl+Enter for submission and Enter for new lines."""

    BINDINGS = [
        ("ctrl+j", "submit", "Submit"),  # Ctrl+Enter often comes as Ctrl+J
    ]

    class Submitted(Message):
        """Message sent when the input is submitted."""
        def __init__(self, sender: Widget, value: str):
            super().__init__()
            self.sender = sender
            self.value = value

    def action_submit(self) -> None:
        """Submit the input (triggered by Ctrl+Enter)."""
        self.post_message(self.Submitted(self, self.text))
