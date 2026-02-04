"""
PromptTextArea Widget

Widget wrapper for MultilineInput that handles multiline input submission.
"""

from typing import Callable
from textual.widget import Widget
from textual.widgets import Static
from .multiline_input import MultilineInput


class PromptTextArea(Widget):
    """Widget wrapper for MultilineInput that handles multiline input submission."""

    can_focus = True
    can_focus_children = True

    DEFAULT_CSS = """
    PromptTextArea {
        width: 100%;
        height: auto;
        padding: 1;
        margin: 1 0;
        background: $surface-lighten-1;
        border: round $accent;
    }

    PromptTextArea > Static {
        width: 100%;
        height: auto;
        margin-bottom: 1;
    }

    PromptTextArea > MultilineInput {
        width: 100%;
        height: auto;
    }

    PromptTextArea .hint-text {
        width: 100%;
        height: auto;
        margin-top: 1;
        color: $text-muted;
    }
    """

    def __init__(self, question: str, default: str, on_submit: Callable[[str], None], **kwargs):
        super().__init__(**kwargs)
        self.question = question
        self.default = default
        self.on_submit_callback = on_submit

    def compose(self):
        yield Static(f"[bold cyan]{self.question}[/bold cyan]")
        yield MultilineInput(
            id="prompt-textarea",
            soft_wrap=True
        )
        yield Static("[dim]Press Enter to submit, Shift+Enter for new line[/dim]", classes="hint-text")

    def on_mount(self):
        """Focus textarea when mounted and set default text."""
        self.call_after_refresh(self._setup_textarea)

    def _setup_textarea(self):
        """Set default text, focus the textarea widget and scroll into view."""
        try:
            textarea = self.query_one(MultilineInput)
            # Set default text AFTER mounting (TextArea doesn't accept text in constructor)
            if self.default:
                textarea.text = self.default
            self.app.set_focus(textarea)
            self.scroll_visible(animate=False)
        except Exception:
            pass

    def on_multiline_input_submitted(self, message: MultilineInput.Submitted):
        """Handle submission from MultilineInput."""
        self.on_submit_callback(message.value)
