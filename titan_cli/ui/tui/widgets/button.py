"""
Button Widget

Reusable button widget with consistent styling and variants.
"""
from textual.widgets import Button as TextualButton


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
