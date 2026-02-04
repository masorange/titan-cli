"""
MultilineInput Widget

Custom TextArea that handles Enter for submission and Shift+Enter for new lines.
"""

from textual.widget import Widget
from textual.widgets import TextArea
from textual.message import Message


class MultilineInput(TextArea):
    """Custom TextArea that handles Enter for submission and Shift+Enter for new lines."""

    class Submitted(Message):
        """Message sent when the input is submitted."""
        def __init__(self, sender: Widget, value: str):
            super().__init__()
            self.sender = sender
            self.value = value

    def on_key(self, event) -> None:
        """Intercept key events before TextArea processes them."""
        # Check if it's Enter WITHOUT shift
        if event.key == "enter" and not event.shift:
            # Submit the input
            self.post_message(self.Submitted(self, self.text))
            event.prevent_default()
            event.stop()
            return

        # For Shift+Enter and all other keys, let TextArea handle it normally
        # (Shift+Enter will create a new line, handled by TextArea)
