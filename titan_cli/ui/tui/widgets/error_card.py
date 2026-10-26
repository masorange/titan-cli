"""
ErrorCard Widget

A bordered container for an error, with the button that copies it to the clipboard
and any actions of the caller's own next to it ("✦ Ask AI to fix"). Usable anywhere
a widget can be mounted; `ctx.textual.error_card(...)` does it from a step. Mods draw
the same card with `titan_cli.core.mods.error_card`.
"""
from typing import Any, Callable, Sequence, Tuple

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Container, Horizontal
from textual.widget import Widget
from textual.widgets import Static

from titan_cli.ui.tui.error_report import describe_error
from titan_cli.ui.tui.icons import Icons
from titan_cli.ui.tui.widgets.button import Button
from titan_cli.ui.tui.widgets.collapsible_list import CopyButton


class ErrorCard(Widget):
    """The error's title, message and details, and "⧉ Copy error" underneath."""

    DEFAULT_CSS = """
    ErrorCard {
        width: 1fr;
        height: auto;
        margin: 0 0 1 0;
    }

    ErrorCard > Container {
        width: 1fr;
        height: auto;
        border: round $error;
        padding: 0 1;
    }

    ErrorCard .error-title {
        text-style: bold;
        color: $error;
    }

    ErrorCard .error-details {
        color: $text-muted;
    }

    ErrorCard .error-actions {
        height: auto;
        margin-top: 1;
    }

    ErrorCard .error-actions CopyButton {
        margin-right: 2;
    }

    ErrorCard .error-actions Button {
        margin: 0;
        min-width: 0;
        height: 1;
        border: none;
    }
    """

    def __init__(
        self,
        error: Any,
        title: str = "",
        actions: Sequence[Tuple[str, Callable[[], None]]] = (),
        **kwargs,
    ) -> None:
        """
        Args:
            error: A message, an engine `Error`, a `ClientError` or an exception.
            title: Optional line above the message ("Workflow failed at step 'push'").
            actions: Extra buttons after Copy, as (label, on_press) pairs. Each runs on
                the UI thread, so hand slow work to a worker.
        """
        super().__init__(**kwargs)
        self.report = describe_error(error, title)
        self._actions = list(actions)
        self._action_by_button = {}

    def on_button_pressed(self, event: Button.Pressed) -> None:
        action = self._action_by_button.get(event.button)
        if action is not None:
            event.stop()
            action()

    def compose(self) -> ComposeResult:
        # `Text` and not a str: an error often has [brackets] that Rich markup would eat.
        with Container():
            if self.report.title:
                yield Static(Text(f"{Icons.ERROR} {self.report.title}"), classes="error-title")
                yield Static(Text(self.report.message))
            else:
                yield Static(Text(f"{Icons.ERROR} {self.report.message}"), classes="error-title")
            if self.report.details:
                yield Static(Text("\n".join(self.report.details)), classes="error-details")
            with Horizontal(classes="error-actions"):
                yield CopyButton(self.report.as_text(), "error", caption="Copy error")
                for label, on_press in self._actions:
                    button = Button(label, variant="default")
                    self._action_by_button[button] = on_press
                    yield button
