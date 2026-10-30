"""
InputField: a one-line text field for panes and workspaces, backed by Textual's own `Input`.
"""
from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import Input as TextualInput

from titan_cli.core.logging import get_logger
from titan_cli.ui.elements import Input

logger = get_logger(__name__)


class InputField(Widget, can_focus=True, can_focus_children=True):
    """A one-line text field, backed by Textual's own `Input`; runs the mod's `on_change`
    on every keystroke and `on_submit` (if any) on Enter."""

    # Textual's own Input has a 3-row bordered box with its own, more specific rules;
    # `!important` beats those so it fits the pane's one-line-per-control rhythm.
    DEFAULT_CSS = """
    InputField {
        width: 1fr;
        height: 1;
    }
    InputField > Input {
        border: none !important;
        height: 1 !important;
        padding: 0 !important;
        background: $surface-lighten-1;
    }
    InputField.-normal {
        height: 3;
    }
    InputField.-normal > Input {
        border: round $primary !important;
        height: 3 !important;
        padding: 0 1 !important;
    }
    """

    def __init__(self, element: Input):
        super().__init__()
        self._element = element
        self.set_class(element.size == "normal", "-normal")

    def compose(self) -> ComposeResult:
        yield TextualInput(value=self._element.value, placeholder=self._element.placeholder)

    def apply(self, element: Input) -> None:
        """Take a redrawn input's handlers; only reset the shown value when it actually
        changed from outside (an own keystroke already matches, so the cursor stays put)."""
        self._element = element
        self.set_class(element.size == "normal", "-normal")
        field = self.query_one(TextualInput)
        if field.value != element.value:
            field.value = element.value
        field.placeholder = element.placeholder

    def on_input_changed(self, event: TextualInput.Changed) -> None:
        event.stop()
        try:
            self._element.on_change(event.value)
        except Exception:
            logger.exception("mod_input_failed")

    def on_input_submitted(self, event: TextualInput.Submitted) -> None:
        event.stop()
        if self._element.on_submit is None:
            return
        try:
            self._element.on_submit(event.value)
        except Exception:
            logger.exception("mod_input_failed")
