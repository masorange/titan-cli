"""
What a `ui.render` hook answers with: a small tree of plain values.

Mods describe *what* to show; the TUI decides how. Keeping the tree free of
Textual widgets means a mod never touches the widget tree, cannot break the
layout around its slot, and can be tested without mounting anything.

Colors are semantic names the TUI maps onto its theme:
`primary`, `accent`, `success`, `warning`, `error`, `info`, `subtle`.
Falsy children (`None`, `False`, `""`, `0`, `[]`) are dropped and lists are
flattened, so conditionals and comprehensions read naturally:

    Box(Text("PRs", bold=True), has_error and Text(err, color="error"))
"""

from dataclasses import dataclass
from typing import Callable, Optional, Tuple, Union

Child = Union["Text", "Box", "Button", str, None, bool]


def _children(children) -> tuple:
    """Flatten nested lists and drop falsy values, so `cond and Text(...)` is safe even when cond is 0 or []."""
    out = []
    for child in children:
        if isinstance(child, (list, tuple)):
            out.extend(_children(child))
        elif child:
            out.append(child)
    return tuple(out)


@dataclass(frozen=True)
class Text:
    """A line of text. Parts are strings or nested `Text` spans with their own style."""

    parts: Tuple[Union[str, "Text"], ...]
    color: Optional[str] = None
    bold: bool = False
    dim: bool = False
    wrap: bool = False  # False truncates with an ellipsis at the slot's width

    def __init__(self, *parts, color=None, bold=False, dim=False, wrap=False):
        object.__setattr__(self, "parts", _children(parts))
        object.__setattr__(self, "color", color)
        object.__setattr__(self, "bold", bold)
        object.__setattr__(self, "dim", dim)
        object.__setattr__(self, "wrap", wrap)


@dataclass(frozen=True)
class Box:
    """
    A vertical group; with `border` it gets a rounded frame of that color,
    `indent` shifts it right, and `gap` puts blank lines between children.
    """

    children: Tuple[Child, ...]
    border: Optional[str] = None
    row: bool = False  # lay children out left to right, spread across the width
    indent: int = 0
    gap: int = 0

    def __init__(self, *children, border=None, row=False, indent=0, gap=0):
        object.__setattr__(self, "children", _children(children))
        object.__setattr__(self, "border", border)
        object.__setattr__(self, "row", row)
        object.__setattr__(self, "indent", indent)
        object.__setattr__(self, "gap", gap)


@dataclass(frozen=True)
class Button:
    """
    A pressable line. `on_press` runs on the UI thread: keep it to a state update.

    `action` draws it as a button (a filled chip as wide as its label) for
    something that does work, such as running a workflow; a plain one reads as
    a line of the pane, right for a fold or a picker.
    """

    label: str
    on_press: Callable[[], None]
    dim: bool = False
    action: bool = False
