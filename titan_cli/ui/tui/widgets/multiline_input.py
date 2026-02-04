"""
MultilineInput Widget

Custom TextArea that handles Enter for submission and Shift+Enter for new lines.
"""

from textual.widget import Widget
from textual.widgets import TextArea
from textual.message import Message


class MultilineInput(TextArea):
    """Custom TextArea that handles Ctrl+Enter for submission and Enter for new lines."""

    class Submitted(Message):
        """Message sent when the input is submitted."""
        def __init__(self, sender: Widget, value: str):
            super().__init__()
            self.sender = sender
            self.value = value

    def _on_key(self, event) -> None:
        """Intercept key events at low level before TextArea processes them."""
        # Use Ctrl+D for submit (standard in many CLI tools)
        if event.key == "ctrl+d":
            self.post_message(self.Submitted(self, self.text))
            event.prevent_default()
            event.stop()
            return

        # Let TextArea handle everything else (Enter creates new lines)
        super()._on_key(event)
