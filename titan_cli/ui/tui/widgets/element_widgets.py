"""
Widgets for elements: the tree of plain values (`titan_cli.ui.elements`) drawn as Textual widgets.

Every widget here is `Updatable`: it is built from an element and can be handed a redrawn one
with `apply`, so a repaint patches what is on screen instead of remounting it (no flash, a
focused button keeps its focus, a field keeps its cursor). `build`, `patch` and `reconcile`
do that for a whole tree and know nothing of any panel: a mod's side panel and a workspace
both use them.
"""
import time
from typing import Any, List

from rich.text import Text as RichText
from textual.containers import Horizontal, Vertical
from textual.widget import Widget

from titan_cli.ui.elements import Box, Columns, Component, column_widths, dragged_widths
from titan_cli.ui.elements import Button as ButtonElement
from titan_cli.ui.elements import Input, Link, Text, plain
from titan_cli.ui.tui.widgets import diff_view  # noqa: F401  (registers the `titan.diff` widget)
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


DRAG_THROTTLE = 0.03  # seconds between two layouts while a column border is dragged


class _Columns(Horizontal):
    DEFAULT_CSS = """
    _Columns {
        height: auto;
        width: 1fr;
    }
    """

    element: Columns


class _Column(Vertical):
    """One column. With `on_resize` on its `Columns`, its left border is a handle: drag it to resize."""

    DEFAULT_CSS = """
    _Column {
        height: auto;
    }
    """

    _drag = None  # (index, screen_x at press, widths at press) while a drag is on
    _drag_applied = None  # the widths the drag last laid out, and when: a move that changes nothing costs nothing

    def _owner_and_index(self):
        owner = self.parent
        if not isinstance(owner, _Columns) or getattr(owner, "element", None) is None:
            return None, 0
        return owner, [c for c in owner.children if isinstance(c, _Column)].index(self)

    def on_mouse_down(self, event) -> None:
        owner, i = self._owner_and_index()
        if owner is None or not i or not owner.element.on_resize or event.x != 0:
            return
        columns = [c for c in owner.children if isinstance(c, _Column)]
        self._drag = (i, event.screen_x, tuple(c.region.width for c in columns))
        self.styles.border_left = ("vkey", COLORS["accent"])
        self.capture_mouse()
        event.stop()

    def on_mouse_move(self, event) -> None:
        if self._drag is None:
            return
        owner, _ = self._owner_and_index()
        i, start, widths = self._drag
        self._apply_widths(owner, dragged_widths(widths, i, event.screen_x - start))
        event.stop()

    def _apply_widths(self, owner, sizes, final: bool = False) -> None:
        """
        Lay the columns out at `sizes` in one repaint. Mouse moves arrive faster than a heavy screen
        can lay out, so a move inside the throttle window is skipped (the last one is applied on release).
        """
        last = _Column._drag_applied
        now = time.monotonic()
        if not final and last and (last[0] == sizes or now - last[1] < DRAG_THROTTLE):
            return
        _Column._drag_applied = (sizes, now)
        with self.app.batch_update():
            for column, w in zip([c for c in owner.children if isinstance(c, _Column)], sizes):
                column.styles.width = f"{w}fr"

    def on_mouse_up(self, event) -> None:
        if self._drag is None:
            return
        owner, _ = self._owner_and_index()
        i, start, widths = self._drag
        self._drag = None
        self.styles.border_left = ("vkey", COLORS["subtle"])
        self.release_mouse()
        event.stop()
        resized = dragged_widths(widths, i, event.screen_x - start)
        self._apply_widths(owner, resized, final=True)
        _Column._drag_applied = None
        if resized != widths and owner.element.on_resize:
            owner.element.on_resize(resized)


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
    _Row.-with-input > Static:last-of-type,
    _Row.-pack > Static,
    _Row.-pack > Static:last-of-type {
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


def fill_height(body: Widget) -> None:
    """
    Make the columns inside a scrolling `body` reach its bottom edge, so a draggable border runs the
    whole screen instead of stopping where the shortest column's content does. Call it after a
    layout: it reads where the columns start. A column taller than the screen is left as it is.
    Columns without `on_resize` have no border to drag: they keep the height of their content, so
    several rows of columns (a month grid) stack instead of each one filling the screen.
    """
    for columns in body.query(_Columns):
        if not getattr(columns.element, "on_resize", None):
            for column in columns.children:
                if isinstance(column, _Column) and column.styles.min_height is not None:
                    column.styles.clear_rule("min_height")  # the row used to be draggable, or a patched one was
            continue
        top = columns.region.y - body.region.y + body.scroll_y
        room = max(0, body.scrollable_content_region.height - top)
        for column in columns.children:
            if not isinstance(column, _Column):
                continue
            shown = column.styles.min_height
            if shown is None or shown.value != room:
                column.styles.min_height = room


def kind(element: Any) -> type:
    """The widget class `build` makes for an element: a widget of that class can be patched to it."""
    if isinstance(element, ButtonElement):
        return Button if element.variant else PressableRow
    if isinstance(element, Input):
        return InputField
    if isinstance(element, Component):
        return widget_for(element.name) or Line
    if isinstance(element, Columns):
        return _Columns
    if isinstance(element, Box):
        if _is_spread(element):
            return Line
        return _Row if element.row else _Group
    return Line


def _is_spread(box: Box) -> bool:
    return box.row and not box.pack and bool(box.children) and all(isinstance(c, Text) for c in box.children)


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


def _column(element: Columns, i: int, width: int) -> tuple:
    """The width column `i` of `element` is drawn for, and its share of the row (`fr`)."""
    return column_widths(width, element.ratio, element.gap)[i], element.ratio[i]


def _style_column(column: Widget, element: Columns, i: int) -> None:
    # A repaint that lands mid-drag must not snap the columns back to the old ratio.
    if _Column._drag_applied is None:
        column.styles.width = f"{element.ratio[i]}fr"
    handle = bool(i and element.on_resize)
    # A draggable column's left border is the gap: a thin line that is the handle.
    column.styles.margin = (0, 0, 0, element.gap - 1 if handle else element.gap if i else 0)
    if handle:
        if column._drag is None:
            column.styles.border_left = ("vkey", COLORS["subtle"])
    else:
        column.styles.clear_rule("border_left")


def _inner_width(box: Box, width: int) -> int:
    return (width - 4 if box.border else width) - box.indent


def _style_box(widget: Widget, box: Box, children: List[Widget]) -> None:
    """Inline styles for a box; a style the box does not ask for is cleared, so the CSS shows through."""
    if isinstance(widget, _Row):
        # A row with a text field is a label/field line, not a title-and-value spread.
        widget.set_class(any(isinstance(c, Input) for c in box.children), "-with-input")
        widget.set_class(box.pack, "-pack")
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
    if cls is _Columns:
        columns = []
        for i, child in enumerate(element.children):
            column = _Column(build(child, _column(element, i, width)[0]))
            _style_column(column, element, i)
            columns.append(column)
        widget = _Columns(*columns)
        widget.element = element
        return widget
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
    if cls is _Columns:
        columns = live_children(widget)
        if len(columns) != len(element.children):
            return False
        for i, (column, child) in enumerate(zip(columns, element.children)):
            reconcile(column, [child], _column(element, i, width)[0])
            _style_column(column, element, i)
        widget.element = element
        widget.refresh(layout=True)
    elif isinstance(element, Component) and cls is not Line:
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
