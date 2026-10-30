"""
Button Widget

Reusable button widget with consistent styling and variants.
"""
from typing import Any, Callable, Optional

from textual.widgets import Button as TextualButton

from titan_cli.core.logging import get_logger
from titan_cli.ui.elements import plain

logger = get_logger(__name__)

VARIANTS = ("primary", "default", "success", "warning", "error")
SIZES = ("normal", "compact")


class Button(TextualButton):
    """
    Custom Button widget with consistent styling.

    Fixes the focus issue (black box around text) and provides consistent variants.

    Usage:
        Button("Click Me", variant="primary", id="my-button")
        Button("Delete", variant="error")
        Button("Cancel", variant="default")

    Available variants:
        - primary: Primary action button (blue/accent color)
        - default: Default button (neutral)
        - error: Destructive action (red)
        - success: Success action (green)
        - warning: Warning action (yellow)

    Available sizes (`size=`):
        - normal: three rows with a border
        - compact: one row, no border, as wide as its label: for a pane that puts one under
          every item

    With `on_press` the button runs that callback itself and stops the event; without it the
    event bubbles as Textual's own button does. The widget is `Updatable`: `apply` takes an
    element `Button` (`label`, `on_press`, `variant`) and keeps the widget, so a focused button
    stays focused across a repaint.
    """

    DEFAULT_CSS = """
    Button {
        min-width: 16;
        height: 3;
        margin: 0 1;
    }

    Button:focus {
        text-style: none;
    }

    /* Titan's button is three rows with tall borders per variant and on hover;
       `!important` beats those more specific rules. */
    Button.-compact {
        width: auto;
        min-width: 0;
        height: 1 !important;
        border: none !important;
        padding: 0 1;
        margin: 0 1 0 0;
    }

    Button.-primary {
        background: $primary;
        color: $text;
    }

    Button.-primary:hover {
        background: $primary-lighten-1;
    }

    Button.-primary:focus {
        background: $primary;
        text-style: none;
    }

    Button.-default {
        background: $surface-lighten-2;
        color: $text;
    }

    Button.-default:hover {
        background: $surface-lighten-3;
    }

    Button.-default:focus {
        background: $surface-lighten-2;
        text-style: none;
    }

    Button.-error {
        background: $error;
        color: $text;
    }

    Button.-error:hover {
        background: $error-lighten-1;
    }

    Button.-error:focus {
        background: $error;
        text-style: none;
    }

    Button.-success {
        background: $success;
        color: $text;
    }

    Button.-success:hover {
        background: $success-lighten-1;
    }

    Button.-success:focus {
        background: $success;
        text-style: none;
    }

    Button.-warning {
        background: $warning;
        color: $text;
    }

    Button.-warning:hover {
        background: $warning-lighten-1;
    }

    Button.-warning:focus {
        background: $warning;
        text-style: none;
    }
    """

    def __init__(
        self,
        label: Any = None,
        variant: str = "default",
        *,
        size: str = "normal",
        on_press: Optional[Callable[[], None]] = None,
        **kwargs,
    ):
        super().__init__(label, variant=self._variant(variant), **kwargs)
        self._on_press = on_press
        self.set_class(size == "compact", "-compact")

    @staticmethod
    def _variant(variant: Optional[str]) -> str:
        return variant if variant in VARIANTS else "default"

    def apply(self, props: Any) -> None:
        """Take a redrawn element `Button`'s label, variant and handler."""
        self._on_press = props.on_press
        self.label = plain(props.label)
        self.variant = self._variant(props.variant)

    def on_button_pressed(self, event: TextualButton.Pressed) -> None:
        if self._on_press is None:
            return
        event.stop()
        try:
            self._on_press()
        except Exception:
            logger.exception("button_press_failed", label=str(self.label))
