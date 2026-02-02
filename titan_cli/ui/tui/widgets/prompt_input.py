"""
PromptInput Widget

Widget wrapper for Input that handles submission events.
"""

from typing import Callable
from textual.widget import Widget
from textual.widgets import Input, Static


class PromptInput(Widget):
    """Widget wrapper for Input that handles submission events."""

    # Allow this widget and its children to receive focus
    can_focus = True
    can_focus_children = True

    DEFAULT_CSS = """
    PromptInput {
        width: 100%;
        height: auto;
        padding: 1;
        margin: 1 0;
        background: $surface-lighten-1;
        border: round $accent;
    }

    PromptInput > Static {
        width: 100%;
        height: auto;
        margin-bottom: 1;
    }

    PromptInput > Input {
        width: 100%;
    }
    """

    def __init__(self, question: str, default: str, placeholder: str, on_submit: Callable[[str], None], **kwargs):
        super().__init__(**kwargs)
        self.question = question
        self.default = default
        self.placeholder = placeholder
        self.on_submit_callback = on_submit

    def compose(self):
        yield Static(f"[bold cyan]{self.question}[/bold cyan]")
        yield Input(
            value=self.default,
            placeholder=self.placeholder,
            id="prompt-input"
        )

    def on_mount(self):
        """Focus input when mounted and scroll into view."""
        # Use call_after_refresh to ensure widget tree is ready
        self.call_after_refresh(self._focus_input)

    def _focus_input(self):
        """Focus the input widget and scroll into view."""
        try:
            input_widget = self.query_one(Input)
            # Use app.set_focus() to force focus change from steps-panel
            self.app.set_focus(input_widget)
            # Scroll to make this widget visible
            self.scroll_visible(animate=False)
        except Exception:
            pass

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle input submission."""
        value = event.value
        self.on_submit_callback(value)
