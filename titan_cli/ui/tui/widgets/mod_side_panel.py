"""
Side panel for mods.

Docked on the right of every BaseScreen; shows the panes mods open with
`m.ui.open(...)`, each drawn from the element tree its `ui.render` hook
answers. The panel only translates that tree into widgets: what is in it,
and when it changes, is the mods' business (their `m.state`). Collapsing it
(F4, or a click on its header) leaves only the rail; dragging its left
border resizes it, on every screen at once.

Panes do not stack: a rail on the right edge holds one icon per pane, and
the panel shows the one picked there (clicking the shown one folds it).
"""
from typing import Any, List

from rich.style import Style
from rich.text import Text as RichText
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widget import Widget
from textual.widgets import Static

from titan_cli.core.logging import get_logger
from titan_cli.core.mods.elements import Box, Button, Link, Text
from titan_cli.ui.tui import colors
from titan_cli.ui.tui.widgets.button import Button as TitanButton

logger = get_logger(__name__)

PANEL_WIDTH = 56
MIN_PANEL_WIDTH = 24
MIN_MAIN_WIDTH = 40  # what a drag must leave to the screen's own content
RAIL_WIDTH = 4  # an emoji is two cells wide, plus a margin on each side
COLLAPSED_WIDTH = RAIL_WIDTH + 1  # the rail and the panel's left border

_COLORS = {
    "primary": colors.PRIMARY,
    "accent": colors.ACCENT,
    "success": colors.SUCCESS,
    "warning": colors.WARNING,
    "error": colors.ERROR,
    "info": colors.INFO,
    "subtle": colors.TEXT_MUTED,
}


def clamp_panel_width(requested: int, screen_width: int) -> int:
    """The width a drag may give the panel on a screen this wide."""
    widest = max(MIN_PANEL_WIDTH, screen_width - MIN_MAIN_WIDTH)
    return max(MIN_PANEL_WIDTH, min(requested, widest))


def _color(name: Any) -> Any:
    return _COLORS.get(name, name) if name else None


def to_rich(text: Text, inherited: Style = Style()) -> RichText:
    """Flatten a `Text` element, nested spans included, into one Rich Text."""
    style = inherited + Style(
        color=_color(text.color), bold=text.bold or None, dim=text.dim or None
    )
    out = RichText(no_wrap=not text.wrap, overflow="fold" if text.wrap else "ellipsis")
    for part in text.parts:
        if isinstance(part, Text):
            out.append_text(to_rich(part, style))
        elif isinstance(part, Link):
            out.append_text(link_text(part, style))
        else:
            out.append(str(part), style)
    return out


def link_text(link: Link, inherited: Style = Style()) -> RichText:
    """A link's label, underlined; a click runs the `open_link` action of the line holding it."""
    style = inherited + Style(color=_color("info"), underline=True) + Style.from_meta(
        {"@click": f"open_link({link.url!r})"}
    )
    return RichText(link.label, style=style)


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
    """


class _Line(Static):
    DEFAULT_CSS = """
    _Line {
        height: auto;
        width: 1fr;
    }
    """

    def action_open_link(self, url: str) -> None:
        # A mod's URL: only the web, never file:// or a custom scheme handler.
        if not url.startswith(("https://", "http://")):
            logger.warning("mod_link_refused", url=url)
            return
        self.app.open_url(url)


class _Pressable(_Line, can_focus=True):
    """A line that runs a mod's `on_press` on click or Enter."""

    BINDINGS = [("enter", "press", "Toggle")]

    DEFAULT_CSS = """
    _Pressable:hover, _Pressable:focus {
        background: $boost;
    }
    """

    def __init__(self, button: Button):
        super().__init__(self._label(button))
        self._button = button

    @staticmethod
    def _label(button: Button) -> RichText:
        style = Style(dim=True) if button.dim else Style()
        return RichText(button.label, style=style, no_wrap=True, overflow="ellipsis")

    def set_button(self, button: Button) -> None:
        """Take a redrawn button's label and handler, keeping this widget (and its focus)."""
        self._button = button
        self.update(self._label(button))

    def on_click(self) -> None:
        self.action_press()

    def action_press(self) -> None:
        try:
            self._button.on_press()
        except Exception:
            logger.exception("mod_button_failed", label=self._button.label)


class _ModButton(TitanButton):
    """
    A `Button` with a variant, drawn as Titan's own button in its colours but one
    row tall, so a pane can put one under every item; runs the mod's `on_press`.
    """

    VARIANTS = ("primary", "default", "success", "warning", "error")

    # Titan's button is three rows with tall borders per variant and on hover;
    # `!important` beats those more specific rules.
    DEFAULT_CSS = """
    _ModButton {
        width: auto;
        min-width: 0;
        height: 1 !important;
        border: none !important;
        padding: 0 1;
        margin: 0 1 0 0;
    }
    """

    def __init__(self, button: Button):
        super().__init__(button.label, variant=self._variant(button))
        self._button = button

    @classmethod
    def _variant(cls, button: Button) -> str:
        return button.variant if button.variant in cls.VARIANTS else "default"

    def set_button(self, button: Button) -> None:
        self._button = button
        self.label = button.label
        self.variant = self._variant(button)

    def on_button_pressed(self, event: TitanButton.Pressed) -> None:
        event.stop()
        try:
            self._button.on_press()
        except Exception:
            logger.exception("mod_button_failed", label=self._button.label)


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
    if isinstance(element, Button):
        return _ModButton if element.variant else _Pressable
    if isinstance(element, Box):
        if _is_spread(element):
            return _Line
        return _Row if element.row else _Group
    return _Line


def _is_spread(box: Box) -> bool:
    return box.row and bool(box.children) and all(isinstance(c, Text) for c in box.children)


def _line_text(element: Any, width: int) -> RichText:
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
        widget.styles.border = ("round", _color(box.border))
    else:
        # `border` is a shorthand stored per edge.
        for edge in ("border_top", "border_right", "border_bottom", "border_left"):
            widget.styles.clear_rule(edge)


def build(element: Any, width: int) -> Widget:
    """Turn one element of a mod's tree into a widget `width` columns wide."""
    cls = kind(element)
    if cls in (_Pressable, _ModButton):
        return cls(element)
    if cls is _Line:
        return _Line(_line_text(element, width))
    children = [build(child, _inner_width(element, width)) for child in element.children]
    widget = cls(*children)
    _style_box(widget, element, children)
    return widget


def live_children(widget: Widget) -> List[Widget]:
    """Children not already on their way out (removal finishes on a later tick)."""
    return [c for c in widget.children if not getattr(c, "_pruning", False)]


def patch(widget: Widget, element: Any, width: int) -> bool:
    """Bring a mounted widget in line with a redrawn element without remounting it.

    False when the widget is of another kind: the caller replaces it.
    """
    cls = kind(element)
    if type(widget) is not cls:
        return False
    if cls in (_Pressable, _ModButton):
        widget.set_button(element)
    elif cls is _Line:
        widget.update(_line_text(element, width))
    else:
        reconcile(widget, list(element.children), _inner_width(element, width))
        _style_box(widget, element, live_children(widget))
        widget.refresh(layout=True)  # cleared inline rules do not repaint by themselves
    return True


def reconcile(container: Widget, elements: List[Any], width: int) -> None:
    """Make `container`'s children match `elements`, position by position.

    Each child that can be patched is updated in place, so nothing on screen is
    torn down and remounted (no flash) and a focused button keeps its focus; only
    children of another kind are replaced, and the surplus at the end added or removed.
    """
    current = live_children(container)
    for i, element in enumerate(elements):
        if i < len(current):
            old = current[i]
            if not patch(old, element, width):
                container.mount(build(element, width), before=old)
                old.remove()
        else:
            container.mount(build(element, width))
    for old in current[len(elements):]:
        old.remove()


class _RailIcon(Static, can_focus=True):
    """A pane's icon on the rail: click or Enter shows that pane (or folds it when shown)."""

    BINDINGS = [("enter", "select", "Show")]

    DEFAULT_CSS = """
    _RailIcon {
        width: 1fr;
        height: 3;  /* odd, so the icon has a middle row */
        content-align: center middle;
    }
    _RailIcon:hover, _RailIcon:focus {
        background: $boost;
    }
    _RailIcon.-active {
        background: $primary 40%;
    }
    """

    def __init__(self, pane: str, title: str, icon: str):
        super().__init__(RichText(icon, no_wrap=True, overflow="crop"))
        self.pane = pane
        self.tooltip = title

    def on_click(self, event) -> None:
        event.stop()
        self.action_select()

    def action_select(self) -> None:
        self.app.mods_host.select(self.pane)


class ModSidePanel(Horizontal):
    DEFAULT_CSS = f"""
    ModSidePanel {{
        dock: right;
        width: {PANEL_WIDTH};
        height: 1fr;
        border-left: tall $primary 40%;
        background: $surface;
    }}
    ModSidePanel.-resizing {{
        border-left: tall $primary;
    }}
    ModSidePanel #mod-panel-content {{
        width: 1fr;
        height: 1fr;
    }}
    ModSidePanel.-collapsed #mod-panel-content {{
        display: none;
    }}
    ModSidePanel #mod-panel-rail {{
        width: {RAIL_WIDTH};
        height: 1fr;
        background: $surface-darken-1;
    }}
    ModSidePanel #mod-panel-header {{
        height: 1;
        width: 1fr;
        background: $surface-lighten-1;
        text-style: bold;
    }}
    ModSidePanel #mod-panel-header:hover {{
        background: $boost;
    }}
    ModSidePanel #mod-panel-body {{
        height: 1fr;
        padding: 0 1;
    }}
    """

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._resizing = False
        self._rail_panes: List[str] = []
        self._shown: Any = None

    def compose(self) -> ComposeResult:
        with Vertical(id="mod-panel-content"):
            yield Static(id="mod-panel-header")
            yield VerticalScroll(id="mod-panel-body")
        yield Vertical(id="mod-panel-rail")

    # Column 0 is the left border: pressing there starts a resize, and the mouse
    # stays captured until it is released, wherever the pointer goes meanwhile.
    def on_mouse_down(self, event) -> None:
        host = getattr(self.app, "mods_host", None)
        if host is None or host.collapsed or event.x != 0:
            return
        self._resizing = True
        self.add_class("-resizing")
        self.capture_mouse()
        event.stop()

    def on_mouse_move(self, event) -> None:
        if not self._resizing:
            return
        width = clamp_panel_width(self.app.size.width - event.screen_x, self.app.size.width)
        self.app.mods_host.width = width
        self.styles.width = width
        event.stop()

    def on_mouse_up(self, event) -> None:
        if not self._resizing:
            return
        self._resizing = False
        self.remove_class("-resizing")
        self.release_mouse()
        event.stop()
        # Panes are laid out for a width: redraw them for the new one.
        self.app.mods_host.repaint("")

    def on_mount(self) -> None:
        self.refresh_panes()

    def on_click(self, event) -> None:
        if getattr(event.widget, "id", None) == "mod-panel-header":
            self.app.mods_host.toggle_collapsed()

    def _refresh_rail(self, host) -> None:
        rail = self.query_one("#mod-panel-rail", Vertical)
        panes = list(host.panes)
        if panes != self._rail_panes:
            rail.remove_children()
            rail.mount_all(_RailIcon(pane, title, icon) for pane, (_, title, icon) in host.panes.items())
            self._rail_panes = panes
        for icon in rail.query(_RailIcon):
            icon.set_class(icon.pane == host.active and not host.collapsed, "-active")

    def refresh_panes(self) -> None:
        host = getattr(self.app, "mods_host", None)
        if host is None or not host.panes:
            self.display = False
            return
        self.display = True
        self.set_class(host.collapsed, "-collapsed")
        self.styles.width = COLLAPSED_WIDTH if host.collapsed else host.width
        self._refresh_rail(host)
        if host.collapsed:
            return

        pane = host.active if host.active in host.panes else next(iter(host.panes))
        _, title, _ = host.panes[pane]
        header = self.query_one("#mod-panel-header", Static)
        header.update(RichText(f"▸ {title}  (F4)", no_wrap=True, overflow="ellipsis"))

        body = self.query_one("#mod-panel-body", VerticalScroll)
        width = max(10, host.width - RAIL_WIDTH - 3)
        try:
            tree = host.render(pane, width)
        except Exception:
            logger.exception("mod_pane_render_failed", pane=pane)
            tree = Text(f"{pane}: render failed (see log)", color="error")

        with self.app.batch_update():
            reconcile(body, [tree] if tree is not None else [], width)
        # Another pane starts at its top, not where the previous one was scrolled to.
        if pane != self._shown:
            self._shown = pane
            body.scroll_home(animate=False)
