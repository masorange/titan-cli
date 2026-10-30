"""
Widgets for elements: the tree of plain values (`titan_cli.ui.elements`) drawn as Textual widgets.

Every widget here is `Updatable`: it is built from an element and can be handed a redrawn one
with `apply`, so a repaint patches what is on screen instead of remounting it (no flash, a
focused button keeps its focus, a field keeps its cursor). `build`, `patch` and `reconcile`
do that for a whole tree and know nothing of any panel: a mod's side panel and a workspace
both use them.
"""
from typing import Any, List

from rich.text import Text as RichText
from textual.containers import Horizontal, Vertical
from textual.widget import Widget

from titan_cli.ui.elements import Box, Component
from titan_cli.ui.elements import Button as ButtonElement
from titan_cli.ui.elements import Input, Link, Text, plain
from titan_cli.ui.tui.widgets.button import Button
from titan_cli.ui.tui.widgets.element_text import COLORS, Line, link_text, to_rich
from titan_cli.ui.tui.widgets.input_field import InputField
from titan_cli.ui.tui.widgets.pressable_row import PressableRow
from titan_cli.ui.tui.widgets.registry import widget_for
from titan_cli.ui.tui.widgets.updatable import Updatable


class _Group(Vertical):
    DEFAULT_CSS = """
    _Group {
        height: auto;
        width: 1fr;
    }
    _Group.-bordered {
        border: round $primary;
        padding: 0 1;
        margin-bottom: 1;
    }
    """


class _Row(Horizontal):
    DEFAULT_CSS = """
    _Row {
        height: auto;
        width: 1fr;
    }
    _Row > Static {
        width: 1fr;
    }
    _Row > Static:last-of-type {
        text-align: right;
    }
    _Row.-with-input > Static,
    _Row.-with-input > Static:last-of-type {
        width: auto;
        text-align: left;
        margin-right: 1;
    }
    """


def _spread(texts: List[Text], width: int) -> RichText:
    """A row of texts on one line: the first at the left, the rest pushed to the right."""
    left = to_rich(texts[0])
    right = RichText(" ").join(to_rich(t) for t in texts[1:])
    gap = max(1, width - left.cell_len - right.cell_len)
    line = left + RichText(" " * gap) + right
    line.no_wrap, line.overflow = True, "ellipsis"
    return line


def kind(element: Any) -> type:
    """The widget class `build` makes for an element: a widget of that class can be patched to it."""
    if isinstance(element, ButtonElement):
        return Button if element.variant else PressableRow
    if isinstance(element, Input):
        return InputField
    if isinstance(element, Component):
        return widget_for(element.name) or Line
    if isinstance(element, Box):
        if _is_spread(element):
            return Line
        return _Row if element.row else _Group
    return Line


def _is_spread(box: Box) -> bool:
    return box.row and bool(box.children) and all(isinstance(c, Text) for c in box.children)


def _line_text(element: Any, width: int) -> RichText:
    if isinstance(element, Component):
        return to_rich(Text(f"component {element.name!r} is not registered", color="error"))
    if isinstance(element, Text):
        return to_rich(element)
    if isinstance(element, Link):
        return link_text(element)
    if isinstance(element, Box):
        return _spread(list(element.children), width)
    return RichText(str(element), no_wrap=True, overflow="ellipsis")


def _inner_width(box: Box, width: int) -> int:
    return (width - 4 if box.border else width) - box.indent


def _style_box(widget: Widget, box: Box, children: List[Widget]) -> None:
    """Inline styles for a box; a style the box does not ask for is cleared, so the CSS shows through."""
    if isinstance(widget, _Row):
        # A row with a text field is a label/field line, not a title-and-value spread.
        widget.set_class(any(isinstance(c, Input) for c in box.children), "-with-input")
        return
    if box.indent:
        widget.styles.padding = (0, 0, 0, box.indent)
    else:
        widget.styles.clear_rule("padding")
    for i, child in enumerate(children):
        if box.gap and i:
            child.styles.margin = (box.gap, 0, 0, 0)
        else:
            child.styles.clear_rule("margin")
    widget.set_class(bool(box.border), "-bordered")
    if box.border:
        widget.styles.border = ("round", COLORS.get(box.border, box.border))
    else:
        # `border` is a shorthand stored per edge.
        for edge in ("border_top", "border_right", "border_bottom", "border_left"):
            widget.styles.clear_rule(edge)


def build(element: Any, width: int) -> Widget:
    """Turn one element of a mod's tree into a widget `width` columns wide."""
    cls = kind(element)
    if cls is Button:
        return Button(plain(element.label), variant=element.variant, size="compact", on_press=element.on_press)
    if isinstance(element, Component) and cls is not Line:
        return cls(element.props)
    if cls in (PressableRow, InputField):
        return cls(element)
    if cls is Line:
        return Line(_line_text(element, width))
    children = [build(child, _inner_width(element, width)) for child in element.children]
    widget = cls(*children)
    _style_box(widget, element, children)
    return widget


def live_children(widget: Widget) -> List[Widget]:
    """Children not already on their way out (removal finishes on a later tick)."""
    return [c for c in widget.children if not getattr(c, "_pruning", False)]


def patch(widget: Widget, element: Any, width: int) -> bool:
    """Bring a mounted widget in line with a redrawn element without remounting it.

    False when the widget is of another kind, or a box not mounted yet: the caller
    replaces it. A box built on the last repaint holds its children aside until it
    mounts, a tick later; patching it before then would mount them a second time,
    and both copies would show until a later repaint pruned the surplus.
    """
    cls = kind(element)
    if type(widget) is not cls:
        return False
    if cls not in (PressableRow, Button, Line) and not widget.is_mounted:
        return False
    if isinstance(element, Component) and cls is not Line:
        widget.apply(element.props)
    elif issubclass(cls, Updatable):
        widget.apply(element)
    elif cls is Line:
        widget.update(_line_text(element, width))
    else:
        reconcile(widget, list(element.children), _inner_width(element, width))
        _style_box(widget, element, live_children(widget))
        widget.refresh(layout=True)  # cleared inline rules do not repaint by themselves
    return True


def plan_reconcile(current: List[type], elements: List[Any]) -> List[tuple]:
    """What `reconcile` does, position by position, as plain data so it can be tested unmounted.

    `current` are the classes of the mounted children, `elements` the new tree. Each step is
    `("patch", i)` (same kind: apply in place), `("replace", i)` (another kind), `("add", i)`
    (past the end) or `("remove", i)` (surplus mounted children, from the end of `elements` on).
    """
    steps = []
    for i, element in enumerate(elements):
        if i >= len(current):
            steps.append(("add", i))
        elif current[i] is kind(element):
            steps.append(("patch", i))
        else:
            steps.append(("replace", i))
    steps.extend(("remove", i) for i in range(len(elements), len(current)))
    return steps


def reconcile(container: Widget, elements: List[Any], width: int) -> None:
    """Make `container`'s children match `elements`, position by position.

    Each child that can be patched is updated in place, so nothing on screen is
    torn down and remounted (no flash) and a focused button keeps its focus; only
    children of another kind are replaced, and the surplus at the end added or removed.
    """
    current = live_children(container)
    for action, i in plan_reconcile([type(c) for c in current], elements):
        if action == "add":
            container.mount(build(elements[i], width))
        elif action == "remove":
            current[i].remove()
        elif action == "replace" or not patch(current[i], elements[i], width):
            container.mount(build(elements[i], width), before=current[i])
            current[i].remove()
