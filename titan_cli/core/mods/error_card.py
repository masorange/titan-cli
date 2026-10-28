"""The error card for a mod's pane: the error, a button that copies it, and the mod's own actions."""
from typing import Callable, Iterable, Sequence

from .elements import Box, Button, Text


def error_card(
    message: str,
    *,
    copy: Callable[[str, str], None],
    title: str = "",
    details: Iterable[str] = (),
    copy_text: str = "",
    what: str = "error",
    actions: Sequence[Button] = (),
    color: str = "error",
) -> Box:
    """
    A bordered card with an error that can be copied, and buttons of the mod's own.

    `copy` is `m.ui.copy`. What it copies is `copy_text`, or the title, message and
    details when none is given. `actions` are extra buttons next to "⧉ Copy error",
    such as one that asks AI how to fix it.
    """
    details = list(details)
    shown = copy_text or "\n".join([*([title] if title else []), message, *details])
    return Box(
        title and Text(title, bold=True, color=color, wrap=True),
        *[Text(line, color=color, wrap=True) for line in message.splitlines() or [message]],
        *[Text(line, dim=True, wrap=True) for line in details],
        # A line apart, so the buttons read as something to press and not as more of the message.
        Text(" "),
        Box(Button(f"⧉ Copy {what}", lambda: copy(shown, what), dim=True), *actions),
        border=color,
    )
