"""
Dock Widget

The bar at the bottom of every screen, in two rows:

- Launcher, centred: Titan's own destinations (workflows, plugins, AI), reachable from
  any screen, followed by one slot per mod that asked for one with `m.ui.dock`.
- Status: where Titan was started (project, branch) and which AI runs what. The AI
  cells carry the key that changes them, F2 and F3, because this is the only place
  those shortcuts are advertised: a user who can see that the wrong model is selected
  can act on it without leaving the screen they are on.

F6, or a click on the status row's arrow, folds the launcher away and leaves only
the status row; the choice belongs to the app, so every screen's dock follows it.
"""
from typing import Any, Callable, Optional, Sequence, Tuple

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widget import Widget
from textual.widgets import Static

from titan_cli.core.mods import DockSlot
from titan_cli.ui.tui import colors
from titan_cli.ui.tui.icons import Icons

_SEVERITY_COLORS = {
    "primary": colors.PRIMARY,
    "accent": colors.ACCENT,
    "success": colors.SUCCESS,
    "warning": colors.WARNING,
    "error": colors.ERROR,
    "info": colors.INFO,
    "subtle": colors.TEXT_MUTED,
}


Badge = Tuple[str, Optional[str]]  # text, severity

def tile_text(icon: Optional[str], label: str, badges: Sequence[Badge] = ()) -> Text:
    """A tile's two lines: the icon, then the label with each badge in its color."""
    text = Text(justify="center", no_wrap=True, overflow="ellipsis")
    text.append(f"{icon or ' '}\n")
    text.append(label)
    for badge, severity in badges:
        color = _SEVERITY_COLORS.get(severity or "", severity) or colors.ACCENT
        text.append(f" {badge}", style=f"bold {color}")
    return text


def slot_text(slot: DockSlot) -> Text:
    """How a mod's slot reads on its tile."""
    return tile_text(slot.icon, slot.label, [(slot.badge, slot.severity)] if slot.badge else ())


def ai_cells(ai_config: Any, override: Any) -> Tuple[str, str]:
    """
    The F2 and F3 cells: the CLI Titan runs and the model pinned to it, then the
    connection that answers and its model.

    A session override takes a cell over and marks itself with a ●, because it outranks
    everything saved: showing the saved value while something else runs would make the
    dock lie, and an override nobody can see is one they forget is on.
    """
    from titan_cli.ai.constants import get_source_display_name

    connection_id = ai_config.default_connection if ai_config else None
    if override is not None and override.connection:
        connection_id = override.connection

    ai_info = "F3 —"
    if ai_config and connection_id in ai_config.connections:
        connection_cfg = ai_config.connections[connection_id]
        source_name = get_source_display_name(
            connection_cfg.provider or connection_cfg.gateway_backend
        )
        model = connection_cfg.default_model or "default"
        if override is not None and override.connection_model:
            model = override.connection_model
        ai_info = f"F3 {source_name} · {model}"
        if override is not None and (override.connection or override.connection_model):
            ai_info = f"{ai_info} ●"

    # An unset model reads as "default" rather than blank - the CLI still has one,
    # Titan just isn't choosing it.
    cli_info = "F2 —"
    if ai_config and ai_config.default_cli:
        cli = ai_config.default_cli
        cli_info = f"F2 {cli} · {ai_config.cli_models.get(cli) or 'default'}"
    if override is not None and (override.cli or override.cli_model):
        cli = override.cli or (ai_config.default_cli if ai_config else None) or "—"
        model = override.cli_model or (
            ai_config.cli_models.get(cli) if ai_config and cli else None
        )
        cli_info = f"F2 {cli} · {model or 'default'} ●"

    return cli_info, ai_info


class DockItem(Static):
    """One clickable tile of the launcher: icon over label, in a rounded frame."""

    DEFAULT_CSS = """
    DockItem {
        width: auto;
        min-width: 13;
        max-width: 24;
        height: 4;
        padding: 0 1;
        margin: 0 1 0 0;
        border: round $surface-lighten-3;
        background: $surface-lighten-1;
        content-align: center middle;
    }

    DockItem.titan {
        border: round $primary 60%;
    }

    DockItem.-inert:hover {
        border: round $surface-lighten-3;
        background: $surface-lighten-1;
        text-style: none;
    }

    DockItem:hover {
        border: round $primary;
        background: $surface-lighten-2;
        text-style: bold;
    }
    """

    def __init__(self, content: Text, on_press: Callable[[], None], **kwargs):
        super().__init__(content, markup=False, **kwargs)
        self._on_press = on_press

    def on_click(self) -> None:
        self._on_press()


class DockToggle(Static):
    """The status row's arrow: folds or unfolds the launcher."""

    DEFAULT_CSS = """
    DockToggle {
        width: 3;
        padding: 0 1;
        color: $text-muted;
    }

    DockToggle:hover {
        color: $primary;
        text-style: bold;
    }
    """

    def on_click(self) -> None:
        self.app.action_toggle_dock()


class Dock(Widget):
    """
    Titan's bottom bar: a row of tiles over the session's status. Titan's own come
    first, then the mods' own.
    """

    DEFAULT_CSS = """
    /* `split`, not `dock`: a docked bar is painted over the side panel (itself docked
       right, full height), hiding the end of a pane; a split one takes its rows away
       from everything else, so the panel and the screen stop above it. */
    Dock {
        split: bottom;
        height: 5;
        width: 100%;
        background: $surface-lighten-1;
    }

    Dock.-collapsed {
        height: 1;
    }

    Dock.-collapsed #dock-launcher {
        display: none;
    }

    Dock #dock-launcher {
        width: 100%;
        height: 4;
        padding: 0 1;
        align: center top;
    }

    Dock #dock-tiles {
        width: auto;
        height: 4;
        margin: 0 0 0 2;
    }

    Dock #dock-status {
        width: 100%;
        height: 1;
        background: $surface-lighten-2;
    }

    Dock #dock-context {
        width: 1fr;
        padding: 0 1 0 0;
    }

    Dock #dock-ai, Dock #dock-keys {
        width: auto;
        padding: 0 1;
    }

    Dock #dock-keys {
        color: $text-muted;
    }
    """

    def compose(self) -> ComposeResult:
        with Horizontal(id="dock-launcher"):
            yield DockItem(tile_text(Icons.WORKFLOW, "Workflows"), self._run("open_workflows"), classes="titan")
            yield DockItem(tile_text(Icons.PLUGIN, "Plugins"), self._run("open_plugins"), classes="titan")
            yield DockItem(tile_text(Icons.AI_CONFIG, "AI"), self._run("open_ai_config"), classes="titan")
            yield Horizontal(id="dock-tiles")
        with Horizontal(id="dock-status"):
            yield DockToggle("▾", id="dock-toggle")
            yield Static("", id="dock-context", markup=False)
            yield Static("", id="dock-ai")
            yield Static("[b]F4[/b] panel  [b]F6[/b] dock  [b]?[/b] help", id="dock-keys")

    def on_mount(self) -> None:
        self.show_collapsed(getattr(self.app, "dock_collapsed", False))

    def show_collapsed(self, collapsed: bool) -> None:
        """Fold the launcher away (only the status row stays) or bring it back."""
        self.set_class(collapsed, "-collapsed")
        self.query_one("#dock-toggle", DockToggle).update("▸" if collapsed else "▾")

    def _run(self, action: str) -> Callable[[], None]:
        return lambda: getattr(self.app, f"action_{action}")()

    def show_status(self, project: str, branch: str, cli_info: str, ai_info: str) -> None:
        """Repaint the status row; the AI cells come pre-formatted (see BaseScreen)."""
        context = Text()
        context.append(f"{Icons.PROJECT} {project}", style=colors.ORANGE)
        if branch:
            context.append("  ")
            context.append(f"{Icons.GIT_BRANCH} {branch}", style=colors.CYAN)
        self.query_one("#dock-context", Static).update(context)
        ai = Text()
        ai.append(cli_info, style=colors.ACCENT)
        ai.append("    ")
        ai.append(ai_info, style=colors.GREEN)
        self.query_one("#dock-ai", Static).update(ai)

    def refresh_tiles(self) -> None:
        """Redraw the mods' tiles from what they last asked for."""
        self.call_later(self._paint_tiles)

    async def _paint_tiles(self) -> None:
        host = getattr(self.app, "mods_host", None)
        tiles = []
        slots: Sequence[Tuple[str, DockSlot]] = host.dock_slots() if host is not None else ()
        for mod, slot in slots:
            tile = DockItem(slot_text(slot), self._press(host, mod))
            tile.set_class(slot.on_click is None, "-inert")
            tiles.append(tile)
        container = self.query_one("#dock-tiles", Horizontal)
        await container.remove_children()
        await container.mount_all(tiles)

    @staticmethod
    def _press(host: Any, mod: str) -> Callable[[], None]:
        return lambda: host.press_dock(mod)
