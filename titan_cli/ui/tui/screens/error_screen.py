"""
ErrorScreen

Where an error that does not belong to a step is shown: a modal with the ErrorCard
(copy button included) over whatever screen was open. Toasts are informational only,
so `TitanApp.notify(severity="error")` and a mod's error toast open this instead.
"""
from typing import Any

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical, VerticalScroll
from textual.screen import ModalScreen

from titan_cli.ui.tui.widgets import Button, ErrorCard


class ErrorScreen(ModalScreen):
    BINDINGS = [
        Binding("escape", "close", "Close"),
        Binding("enter", "close", "Close", show=False),
    ]

    DEFAULT_CSS = """
    ErrorScreen {
        align: center middle;
        background: $background 60%;
    }

    ErrorScreen > Vertical {
        width: 80%;
        max-width: 100;
        height: auto;
        max-height: 80%;
        background: $surface;
        padding: 1 2;
    }

    ErrorScreen VerticalScroll {
        height: auto;
        max-height: 20;
    }

    ErrorScreen Button {
        margin: 1 0 0 0;
    }
    """

    def __init__(self, error: Any, title: str = "") -> None:
        super().__init__()
        self._card = ErrorCard(error, title)

    def compose(self) -> ComposeResult:
        with Vertical():
            with VerticalScroll():
                yield self._card
            yield Button("Close (Esc)", variant="default", id="error-close")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "error-close":
            event.stop()
            self.dismiss()

    def action_close(self) -> None:
        self.dismiss()
