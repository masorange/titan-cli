"""A strip of tabs: one line of labels, the current one marked, pressing another selects it."""
from typing import Callable, Sequence, Tuple

from titan_cli.ui.elements import Box, Button, Text


def tabs(items: Sequence[Tuple[str, str]], current: str, on_select: Callable[[str], None]) -> Box:
    """
    The strip a screen puts above one pane at a time: `items` are `(key, label)`, `current` the
    key on show, `on_select(key)` runs on a press. The tabs sit at the left at their own width;
    the one on show is bold and marked, the others dim. The strip only draws: what each tab
    holds, and where the current key lives, are the caller's (`w.state`, say).
    """
    return Box(
        *[
            Button(
                Text(Text("▌" if key == current else " ", color="info"), label, bold=key == current,
                     color="info" if key == current else None),
                lambda key=key: on_select(key),
                dim=key != current,
            )
            for key, label in items
        ],
        row=True,
        pack=True,
    )
