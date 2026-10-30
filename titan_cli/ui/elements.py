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
from typing import Any, Callable, Optional, Sequence, Tuple, Union

Child = Union["Text", "Box", "Columns", "Button", "Input", "Link", "Component", str, None, bool]


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
class Link:
    """
    `label` that opens `url` in the browser when clicked. A part of a `Text`
    (`Text(Link("#12", url), " title")`) or a line of its own. Only http(s)
    URLs open.
    """

    label: str
    url: str


@dataclass(frozen=True)
class Text:
    """A line of text. Parts are strings, `Link`s or nested `Text` spans with their own style."""

    parts: Tuple[Union[str, "Text", Link], ...]
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
class Columns:
    """
    Children side by side, each as wide as its share of `ratio` (`(3, 2)`: three fifths and two
    fifths), `gap` columns apart. Each child is drawn for the width it gets: see `column_widths`.
    Use `responsive_columns` to fall back to one column on a narrow screen.
    """

    children: Tuple[Child, ...]
    ratio: Tuple[int, ...] = ()
    gap: int = 1

    def __init__(self, *children, ratio=(), gap=1):
        kept = _children(children)
        object.__setattr__(self, "children", kept)
        object.__setattr__(self, "ratio", tuple(ratio) or (1,) * len(kept))
        object.__setattr__(self, "gap", gap)


def column_widths(width: int, ratio: Tuple[int, ...], gap: int = 1) -> Tuple[int, ...]:
    """How many columns each share of `ratio` gets out of `width`, once the gaps are taken off."""
    usable = max(0, width - gap * (len(ratio) - 1))
    return tuple(max(1, usable * share // sum(ratio)) for share in ratio)


def responsive_columns(
    width: int,
    builders: Sequence[Callable[[int], Child]],
    ratio: Tuple[int, ...] = (),
    collapse_below: int = 120,
    gap: int = 1,
) -> Child:
    """
    `Columns` while `width` is at least `collapse_below`, one column otherwise.

    Each builder gets the width its column has and answers with its tree, so what it draws
    (a card that lays its buttons out by width, say) fits either way. Narrow, the builders
    stack top to bottom at the full width, in order.
    """
    ratio = tuple(ratio) or (1,) * len(builders)
    if width < collapse_below:
        return Box(*[build(width) for build in builders])
    widths = column_widths(width, ratio, gap)
    return Columns(*[build(w) for build, w in zip(builders, widths)], ratio=ratio, gap=gap)


@dataclass(frozen=True)
class Button:
    """
    A pressable line. `on_press` runs on the UI thread: keep it to a state update.

    With a `variant` (`primary`, `default`, `success`, `warning`, `error`) it is
    drawn as Titan's own button, for something that does work such as running a
    workflow; without one it reads as a line of the pane, right for a fold or a
    picker.

    `label` is a string, or a `Text` when parts of the line need their own style
    (a name plain and its date dim, say). A button with a `variant` is drawn by
    Titan's own button widget, which takes a plain label: a `Text` there is
    flattened to its words.
    """

    label: Union[str, "Text"]
    on_press: Callable[[], None]
    dim: bool = False
    variant: Optional[str] = None


@dataclass(frozen=True)
class Component:
    """
    A widget registered by name (`register_widget`), drawn with `props`.

    For what the elements above cannot say: a mod or workspace brings its own widget, and the
    tree names it. A redraw hands the new `props` to the mounted widget's `apply`, so it keeps
    its own state (focus, scroll, typed text). An unregistered name shows a line saying so.
    """

    name: str
    props: Any = None


def plain(label) -> str:
    """A label's words without any styling: what a plain-string widget and a log line get."""
    if isinstance(label, Text):
        return "".join(plain(part) for part in label.parts)
    if isinstance(label, Link):
        return label.label
    return str(label)


@dataclass(frozen=True)
class Input:
    """
    A one-line text field. `on_change` runs on every keystroke, on the UI thread: keep
    it to `m.state`, never a network or disk call. `on_submit`, when given, runs when
    the user presses Enter.

    `size` is `compact` (one line, the default, for a pane) or `normal` (three lines with a
    border, for a field that is the point of a screen, such as a search box).
    """

    value: str
    placeholder: str = ""
    on_change: Callable[[str], None] = lambda value: None
    on_submit: Optional[Callable[[str], None]] = None
    size: str = "compact"
