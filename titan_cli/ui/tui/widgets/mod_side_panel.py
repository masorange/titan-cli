"""
Side panel for mods.

Docked on the right of every BaseScreen; shows the panes mods open with
`m.ui.open(...)`, each drawn from the element tree its `ui.render` hook
answers. The panel only translates that tree into widgets: what is in it,
and when it changes, is the mods' business (their `m.state`). Collapsing it
(F4, or a click on its header) leaves a one-column strip.
"""
from typing import Any, List

from rich.style import Style
from rich.text import Text as RichText
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widget import Widget
from textual.widgets import Static

from titan_cli.core.logging import get_logger
from titan_cli.core.mods.elements import Box, Button, Text
from titan_cli.ui.tui import colors

logger = get_logger(__name__)

PANEL_WIDTH = 48

_COLORS = {
    "primary": colors.PRIMARY,
    "accent": colors.ACCENT,
    "success": colors.SUCCESS,
    "warning": colors.WARNING,
    "error": colors.ERROR,
    "info": colors.INFO,
    "subtle": colors.TEXT_MUTED,
}


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
        else:
            out.append(str(part), style)
    return out


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


class _Pressable(_Line, can_focus=True):
    """A line that runs a mod's `on_press` on click or Enter."""

    BINDINGS = [("enter", "press", "Toggle")]

    DEFAULT_CSS = """
    _Pressable:hover, _Pressable:focus {
        background: $boost;
    }
    """

    def __init__(self, button: Button):
        style = Style(dim=True) if button.dim else Style()
        super().__init__(RichText(button.label, style=style, no_wrap=True, overflow="ellipsis"))
        self._button = button

    def on_click(self) -> None:
        self.action_press()

    def action_press(self) -> None:
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


def build(element: Any, width: int) -> Widget:
    """Turn one element of a mod's tree into a widget `width` columns wide."""
    if isinstance(element, Text):
        return _Line(to_rich(element))
    if isinstance(element, Button):
        return _Pressable(element)
    if isinstance(element, Box):
        if element.row and element.children and all(isinstance(c, Text) for c in element.children):
            return _Line(_spread(list(element.children), width))
        inner = (width - 4 if element.border else width) - element.indent
        children = [build(child, inner) for child in element.children]
        if element.row:
            return _Row(*children)
        group = _Group(*children)
        if element.indent:
            group.styles.padding = (0, 0, 0, element.indent)
        if element.gap:
            for child in children[1:]:
                child.styles.margin = (element.gap, 0, 0, 0)
        if element.border:
            group.add_class("-bordered")
            group.styles.border = ("round", _color(element.border))
        return group
    return _Line(RichText(str(element), no_wrap=True, overflow="ellipsis"))


class ModSidePanel(Vertical):
    DEFAULT_CSS = f"""
    ModSidePanel {{
        dock: right;
        width: {PANEL_WIDTH};
        height: 1fr;
        border-left: tall $primary 40%;
        background: $surface;
    }}
    ModSidePanel.-collapsed {{
        width: 3;
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
    ModSidePanel.-collapsed #mod-panel-body {{
        display: none;
    }}
    """

    def compose(self) -> ComposeResult:
        yield Static(id="mod-panel-header")
        yield VerticalScroll(id="mod-panel-body")

    def on_mount(self) -> None:
        self.refresh_panes()

    def on_click(self, event) -> None:
        if getattr(event.widget, "id", None) == "mod-panel-header":
            self.app.mods_host.toggle_collapsed()

    def refresh_panes(self) -> None:
        host = getattr(self.app, "mods_host", None)
        if host is None or not host.panes:
            self.display = False
            return
        self.display = True
        self.set_class(host.collapsed, "-collapsed")

        header = self.query_one("#mod-panel-header", Static)
        if host.collapsed:
            header.update("◂")
            return
        titles = " · ".join(title for _, title in host.panes.values())
        header.update(RichText(f"▸ {titles}  (F4)", no_wrap=True, overflow="ellipsis"))

        body = self.query_one("#mod-panel-body", VerticalScroll)
        width = max(10, PANEL_WIDTH - 3)
        widgets: List[Widget] = []
        for pane in host.panes:
            try:
                tree = host.render(pane, width)
            except Exception:
                logger.exception("mod_pane_render_failed", pane=pane)
                tree = Text(f"{pane}: render failed (see log)", color="error")
            if tree is not None:
                widgets.append(build(tree, width))

        scroll_y = body.scroll_y
        with self.app.batch_update():
            body.remove_children()
            body.mount_all(widgets)
        body.call_after_refresh(body.scroll_to, y=scroll_y, animate=False)
