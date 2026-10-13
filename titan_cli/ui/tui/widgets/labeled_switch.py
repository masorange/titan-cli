"""
Labeled Switch Widget

Reusable on/off row: Textual's Switch beside a title and an optional description.
"""

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.widget import Widget
from textual.widgets import Static
from textual.widgets import Switch as TextualSwitch


class LabeledSwitch(Widget):
    """
    A switch with its title and description, for settings that are on or off.

    Usage:
        LabeledSwitch("Merge queue", value=True, description="Your place in the queue.",
                      name="queue")

    Emits ``Changed`` (with ``value`` and the widget's ``name``) when toggled by key or
    click; setting ``value`` from code does not emit it. A ``disabled`` row is dimmed and
    cannot be toggled.
    """

    DEFAULT_CSS = """
    LabeledSwitch {
        height: auto;
        padding: 0 1;
        margin-bottom: 1;
    }

    LabeledSwitch > Horizontal {
        height: auto;
    }

    LabeledSwitch Switch {
        margin-right: 1;
        height: 3;
    }

    LabeledSwitch Vertical {
        height: auto;
        min-height: 3;
        width: 1fr;
        align-vertical: middle;
    }

    LabeledSwitch .labeled-switch-title {
        text-style: bold;
        height: auto;
    }

    LabeledSwitch .labeled-switch-description {
        color: $text-muted;
    }

    LabeledSwitch:disabled {
        opacity: 0.5;
    }
    """

    class Changed(Message):
        """The person toggled the switch."""

        def __init__(self, switch: "LabeledSwitch", value: bool) -> None:
            super().__init__()
            self.switch = switch
            self.value = value

    def __init__(
        self,
        label: str,
        value: bool = False,
        description: str = "",
        *,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
        disabled: bool = False,
    ) -> None:
        super().__init__(name=name, id=id, classes=classes, disabled=disabled)
        self._label = label
        self._description = description
        self._initial = value

    def compose(self) -> ComposeResult:
        with Horizontal():
            yield TextualSwitch(value=self._initial)
            with Vertical():
                yield Static(self._label, classes="labeled-switch-title", markup=False)
                if self._description:
                    yield Static(self._description, classes="labeled-switch-description", markup=False)

    @property
    def value(self) -> bool:
        return self.query_one(TextualSwitch).value

    @value.setter
    def value(self, new: bool) -> None:
        with self.prevent(TextualSwitch.Changed):
            self.query_one(TextualSwitch).value = new

    def on_switch_changed(self, event: TextualSwitch.Changed) -> None:
        event.stop()
        self.post_message(self.Changed(self, event.value))
