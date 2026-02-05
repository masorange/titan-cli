"""
PromptTextArea Widget

Widget wrapper for MultilineInput that handles multiline input submission.
"""

from typing import Callable
from textual.widget import Widget
from .multiline_input import MultilineInput
from .text import BoldText, DimText


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

    PromptTextArea > BoldText,
    PromptTextArea > DimText {
        width: 100%;
        height: auto;
        margin-bottom: 1;
    }

    PromptTextArea > MultilineInput {
        width: 100%;
        height: auto;
    }
    """

    def __init__(self, question: str, default: str, on_submit: Callable[[str], None], **kwargs):
        super().__init__(**kwargs)
        self.question = question
        self.default = default
        self.on_submit_callback = on_submit

    def compose(self):
        yield BoldText(self.question)
        yield MultilineInput(
            id="prompt-textarea",
            soft_wrap=True
        )
        yield DimText("Press Ctrl+D to submit, Enter for new line")

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
                # TextArea needs a refresh to recalculate content after text change
                # Call focus/scroll after that refresh
                self.call_after_refresh(self._focus_and_scroll)
            else:
                # No default text, focus immediately
                self._focus_and_scroll()
        except Exception:
            pass

    def _focus_and_scroll(self):
        """Focus and scroll the textarea after it has processed the text."""
        try:
            textarea = self.query_one(MultilineInput)
            self.app.set_focus(textarea)
            self.scroll_visible(animate=False)
        except Exception:
            pass

    def on_multiline_input_submitted(self, message: MultilineInput.Submitted):
        """Handle submission from MultilineInput."""
        self.on_submit_callback(message.value)
