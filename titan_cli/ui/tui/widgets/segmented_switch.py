"""
Segmented Switch Widget

Reusable two-or-more option segmented switch for compact source selection.
"""

from dataclasses import dataclass
from typing import Callable, Optional

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.message import Message
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Static


@dataclass(frozen=True)
class SegmentedSwitchOption:
    """Data model for a segmented switch option."""

    value: str
    label: str


class SegmentedSwitch(Widget):
    """
    Reusable segmented switch with keyboard and mouse interaction.

    Emits a ``Changed`` message when the selected option changes.
    """

    can_focus = True
    value: reactive[str] = reactive("")

    DEFAULT_CSS = """
    SegmentedSwitch {
        width: 30;
        height: auto;
        margin-top: 1;
    }

    SegmentedSwitch > Horizontal {
        width: 100%;
        min-width: 30;
        height: 3;
        background: $surface-lighten-1;
        border: round $primary;
        padding: 0;
        layout: horizontal;
    }

    SegmentedSwitch .segment {
        width: 1fr;
        min-width: 10;
        height: 100%;
        padding: 0 2;
        content-align: center middle;
        text-align: center;
        color: $text-muted;
        background: transparent;
    }

    SegmentedSwitch .segment.-active {
        color: $text;
        background: $primary;
        text-style: bold;
    }

    SegmentedSwitch:focus > Horizontal {
        border: round $accent;
    }

    SegmentedSwitch:focus .segment.-active {
        background: $accent;
    }
    """

    class Changed(Message):
        """Message sent when the selected value changes."""

        def __init__(self, sender: Widget, value: str):
            super().__init__()
            self.sender = sender
            self.value = value

    def __init__(
        self,
        options: list[SegmentedSwitchOption],
        value: Optional[str] = None,
        on_change: Optional[Callable[[str], None]] = None,
        **kwargs,
    ) -> None:
        """
        Initialize the segmented switch.

        Args:
            options: Ordered list of switch options.
            value: Initially selected option value. Defaults to the first option.
            on_change: Optional callback invoked after a user-driven change.
        """
        super().__init__(**kwargs)
        if not options:
            raise ValueError("SegmentedSwitch requires at least one option")

        self.options = options
        self.on_change = on_change
        self._segment_values: dict[str, str] = {}

        option_values = {option.value for option in options}
        initial_value = value if value in option_values else options[0].value
        self.value = initial_value

    def compose(self) -> ComposeResult:
        """Compose the segmented switch UI."""
        with Horizontal():
            for index, option in enumerate(self.options):
                segment_id = f"segment-{index}"
                self._segment_values[segment_id] = option.value
                yield Static(
                    option.label,
                    classes="segment",
                    id=segment_id,
                )

    def on_mount(self) -> None:
        """Sync styles and focus the widget when mounted."""
        self._refresh_segments()
        self.focus()

    def watch_value(self, _: str) -> None:
        """Refresh segment styles when the selected value changes."""
        if self.is_mounted:
            self._refresh_segments()

    def on_click(self, event) -> None:
        """Handle mouse selection of a segment."""
        segment_value = self._segment_values.get(getattr(event.widget, "id", ""))
        if segment_value is not None:
            self._set_value(segment_value, emit=True)
            event.stop()

    def on_key(self, event) -> None:
        """Handle keyboard navigation and selection."""
        if event.key in {"left", "up"}:
            self._move_selection(-1)
            event.stop()
        elif event.key in {"right", "down"}:
            self._move_selection(1)
            event.stop()
        elif event.key == "home":
            self._set_value(self.options[0].value, emit=True)
            event.stop()
        elif event.key == "end":
            self._set_value(self.options[-1].value, emit=True)
            event.stop()

    def set_value(self, value: str) -> None:
        """Update the switch value without emitting a change event."""
        self._set_value(value, emit=False)

    def _move_selection(self, step: int) -> None:
        """Move the active segment left or right."""
        current_index = self._get_index(self.value)
        next_index = max(0, min(len(self.options) - 1, current_index + step))
        self._set_value(self.options[next_index].value, emit=True)

    def _set_value(self, value: str, emit: bool) -> None:
        """Update the selected value and optionally emit a change event."""
        if value == self.value:
            return

        self.value = value
        if emit:
            self._emit_changed()

    def _emit_changed(self) -> None:
        """Emit the changed message and invoke the callback."""
        if self.on_change:
            self.on_change(self.value)
        self.post_message(self.Changed(self, self.value))

    def _get_index(self, value: str) -> int:
        """Return the index for a given option value."""
        for index, option in enumerate(self.options):
            if option.value == value:
                return index
        return 0

    def _refresh_segments(self) -> None:
        """Sync active CSS classes with the current value."""
        for segment in self.query(".segment"):
            segment_value = self._segment_values.get(segment.id or "")
            segment.set_class(segment_value == self.value, "-active")
