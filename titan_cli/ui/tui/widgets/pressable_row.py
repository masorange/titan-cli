"""
PressableRow: a line of text that runs a callback on click or Enter, drawn as a line of its pane
rather than a button (a fold, a picker). Updatable: a redraw swaps its label and callback and
keeps the widget, so a focused row stays focused.
"""
from rich.style import Style
from rich.text import Text as RichText

from titan_cli.core.logging import get_logger
from titan_cli.ui.elements import Button, Text, plain
from titan_cli.ui.tui.widgets.element_text import Line, to_rich

logger = get_logger(__name__)


class PressableRow(Line, can_focus=True):
    """A line that runs an element `Button`'s `on_press` on click or Enter."""

    BINDINGS = [("enter", "press", "Toggle")]

    DEFAULT_CSS = """
    PressableRow:hover, PressableRow:focus {
        background: $boost;
    }
    """

    def __init__(self, button: Button):
        super().__init__(self._label(button))
        self._button = button

    @staticmethod
    def _label(button: Button) -> RichText:
        style = Style(dim=True) if button.dim else Style()
        if isinstance(button.label, Text):
            return to_rich(button.label, style)
        return RichText(button.label, style=style, no_wrap=True, overflow="ellipsis")

    def apply(self, button: Button) -> None:
        """Take a redrawn button's label and handler, keeping this widget (and its focus)."""
        self._button = button
        self.update(self._label(button))

    def on_click(self) -> None:
        self.action_press()

    def action_press(self) -> None:
        try:
            self._button.on_press()
        except Exception:
            logger.exception("mod_button_failed", label=plain(self._button.label))
