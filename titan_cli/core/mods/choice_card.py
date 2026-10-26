"""The choice card for a mod's pane: a bordered card of options, some of which unfold into more."""
from dataclasses import dataclass
from typing import Callable, List, Optional, Sequence

from .elements import Box, Button, Text, plain

# A button with a variant is drawn with a space of padding at each side and one of margin after it.
_CHROME = 3
# What a card's border and padding take off the width of the pane.
_FRAME = 4
# How far an open dropdown's body is shifted right.
_INDENT = 2


@dataclass(frozen=True)
class Option:
    """
    One thing the user can pick.

    With `on_press` it is a pressable option and `variant` is `Button`'s. With
    `options` it is a dropdown: a pressable line (`▸`/`▾`) that shows those options
    under it while open. With `content` (any element of a mod's tree) it is a dropdown
    whose body is yours, such as a small form; `on_open` runs as it opens. `id` names a
    dropdown in the card's state and defaults to its label.
    """

    label: str
    on_press: Optional[Callable[[], None]] = None
    variant: str = "default"
    options: Sequence[Optional["Option"]] = ()
    content: object = None
    id: Optional[str] = None
    on_open: Optional[Callable[[], None]] = None  # a dropdown's: runs when it opens, e.g. to clear a form

    @property
    def is_dropdown(self) -> bool:
        return bool(self.options) or self.content is not None

    @property
    def key(self) -> str:
        return self.id or self.label


def layout(options: Sequence[Option], width: int) -> List[List[Option]]:
    """
    Rows of options for a card `width` columns wide: all on one line when they fit,
    else a grid of equal cells, down to one column when not even two cells fit.
    """
    options = [o for o in options if o]
    if not options:
        return []
    inner = width - _FRAME
    cells = [len(plain(o.label)) + _CHROME for o in options]
    if sum(cells) <= inner:
        return [options]
    columns = max(1, inner // max(cells))
    return [options[i:i + columns] for i in range(0, len(options), columns)]


def choice_card(
    options: Sequence[Optional[Option]],
    *,
    width: int,
    title: str = "",
    hint: str = "",
    state=None,
    key: str = "choice",
    close: bool = True,
    border: str = "subtle",
) -> Optional[Box]:
    """
    A bordered card that asks the user to pick one of `options`.

    `width` is the width of the pane (what `ui.render` receives). Options that sit
    together go on one line when they fit, in a grid of equal cells when they do not,
    and in a column when only one fits. A dropdown (`Option` with `options` or
    `content`) is a line of its own between them; `state` is `m.state`, which keeps
    which dropdown is open under `key` (two cards in one pane need two keys), one at a
    time. `close` folds it again once one of its options is pressed. `None` options
    are dropped, and a card with nothing to say is `None` too, which a parent `Box`
    leaves out.
    """
    options = [o for o in options if o]
    if not (options or title or hint):
        return None
    opened = state.get(key) if state is not None else None

    def pick(option: Option) -> Callable[[], None]:
        def press():
            if close and state is not None:
                state.set(key, None)
            option.on_press()
        return press

    def buttons(group: Sequence[Option], room: int, inside: bool) -> list:
        grid = layout(group, room)
        cell = max((len(plain(o.label)) for o in group), default=0)
        built = []
        for row in grid:
            row_buttons = [
                Button(o.label.ljust(cell) if len(grid) > 1 else o.label,
                       pick(o) if inside else o.on_press, variant=o.variant)
                for o in row
            ]
            built.append(Box(*row_buttons, row=True) if len(row_buttons) > 1 else row_buttons[0])
        return built

    def toggle(option: Option, is_open: bool) -> Callable[[], None]:
        def press():
            if not is_open and option.on_open is not None:
                option.on_open()
            state.set(key, None if is_open else option.key)
        return press

    body = []
    pending: List[Option] = []

    def flush():
        body.extend(buttons(pending, width, False))
        pending.clear()

    for option in options:
        if not option.is_dropdown:
            pending.append(option)
            continue
        flush()
        is_open = opened == option.key
        body.append(Button(f"{'▾' if is_open else '▸'} {option.label}", toggle(option, is_open), dim=True))
        if is_open and option.options:
            inner = [o for o in option.options if o]
            body.append(Box(*buttons(inner, width - _INDENT, True), indent=_INDENT))
        elif is_open:
            body.append(Box(option.content, indent=_INDENT))
    flush()

    return Box(
        title and Text(title, bold=True),
        hint and Text(hint, dim=True, wrap=True),
        *body,
        border=border,
    )
