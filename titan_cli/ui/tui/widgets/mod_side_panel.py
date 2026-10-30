"""
Side panel for mods.

Docked on the right of every BaseScreen; shows the panes mods open with
`m.ui.open(...)`, each drawn from the element tree its `ui.render` hook
answers. The panel only translates that tree into widgets: what is in it,
and when it changes, is the mods' business (their `m.state`). Collapsing it
(F4, or a click on its header) leaves only the rail; dragging its left
border resizes it, on every screen at once.

Panes do not stack: a rail on the right edge holds one icon per pane, and
the panel shows the one picked there (clicking the shown one folds it). A mod
can put a short badge under its pane's icon (`m.ui.badge`), which is what
still tells something with the panel folded.
"""
from typing import Any, List, Optional, Tuple

from rich.text import Text as RichText
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import Static

from titan_cli.core.logging import get_logger
from titan_cli.ui.elements import Text
from titan_cli.ui.tui import colors
from titan_cli.ui.tui.widgets.element_widgets import COLORS, reconcile

logger = get_logger(__name__)

PANEL_WIDTH = 56
MIN_PANEL_WIDTH = 24
MIN_MAIN_WIDTH = 40  # what a drag must leave to the screen's own content
RAIL_WIDTH = 4  # an emoji is two cells wide, plus a margin on each side
SCROLLBAR_WIDTH = 2  # Textual's default vertical scrollbar
COLLAPSED_WIDTH = RAIL_WIDTH + 1  # the rail and the panel's left border


def clamp_panel_width(requested: int, screen_width: int) -> int:
    """The width a drag may give the panel on a screen this wide."""
    widest = max(MIN_PANEL_WIDTH, screen_width - MIN_MAIN_WIDTH)
    return max(MIN_PANEL_WIDTH, min(requested, widest))


def rail_text(icon: str, badge: Optional[Tuple[str, Optional[str]]]) -> RichText:
    """A rail icon's three rows: blank, the icon, then the badge (cut to fit) in its color."""
    text = RichText(f"\n{icon}\n", justify="center", no_wrap=True, overflow="crop")
    if badge:
        label, severity = badge
        text.append(label[:RAIL_WIDTH - 1], style=f"bold {COLORS.get(severity or '', severity) or colors.ACCENT}")
    return text


class _RailIcon(Static, can_focus=True):
    """A pane's icon on the rail: click or Enter shows that pane (or folds it when shown)."""

    BINDINGS = [("enter", "select", "Show")]

    DEFAULT_CSS = """
    _RailIcon {
        width: 1fr;
        height: 3;  /* blank, icon, badge */
    }
    _RailIcon:hover, _RailIcon:focus {
        background: $boost;
    }
    _RailIcon.-active {
        background: $primary 40%;
    }
    """

    def __init__(self, pane: str, title: str, icon: str):
        super().__init__(rail_text(icon, None))
        self.pane = pane
        self.icon = icon
        self.tooltip = title
        self._badge: Optional[Tuple[str, Optional[str]]] = None

    def show_badge(self, badge: Optional[Tuple[str, Optional[str]]]) -> None:
        if badge != self._badge:
            self._badge = badge
            self.update(rail_text(self.icon, badge))

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
        /* The scrollbar's columns are always set aside, so a line laid out for the
           pane's width fits whether or not the pane scrolls. */
        scrollbar-gutter: stable;
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

    def _refresh_rail(self, host, all_panes, badges) -> None:
        rail = self.query_one("#mod-panel-rail", Vertical)
        panes = list(all_panes)
        if panes != self._rail_panes:
            rail.remove_children()
            rail.mount_all(_RailIcon(pane, title, icon) for pane, (_, title, icon) in all_panes.items())
            self._rail_panes = panes
        for icon in rail.query(_RailIcon):
            icon.set_class(icon.pane == host.active and not host.collapsed, "-active")
            icon.show_badge(badges.get(icon.pane))

    def refresh_panes(self) -> None:
        host = getattr(self.app, "mods_host", None)
        # Mods open and close panes from their own threads: read one snapshot.
        all_panes, badges = host.pane_snapshot() if host is not None else ({}, {})
        if not all_panes:
            self.display = False
            return
        self.display = True
        self.set_class(host.collapsed, "-collapsed")
        self.styles.width = COLLAPSED_WIDTH if host.collapsed else host.width
        self._refresh_rail(host, all_panes, badges)
        if host.collapsed:
            return

        pane = host.active if host.active in all_panes else next(iter(all_panes))
        _, title, _ = all_panes[pane]
        header = self.query_one("#mod-panel-header", Static)
        header.update(RichText(f"▸ {title}  (F4)", no_wrap=True, overflow="ellipsis"))

        body = self.query_one("#mod-panel-body", VerticalScroll)
        # Less the panel's left border (1), the body's padding (2) and its scrollbar (2):
        # a row spread to more than that is cut at the right edge, where the price is.
        width = max(10, host.width - RAIL_WIDTH - 1 - 2 - SCROLLBAR_WIDTH)
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
