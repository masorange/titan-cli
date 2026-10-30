"""
Workspace screen: one workspace's whole screen, drawn from the element tree its view answers.

Opened by `w.ui.open_workspace` (its dock tile does it) and left with `Esc`. Titan provides the
container, the header and the dock; what is inside, and when it changes (its `w.state`), is the
workspace's business. The tree is drawn with the same widgets as a mod's pane and repainted in
place, so a focused button or a half-typed field survives a redraw.
"""
from textual.app import ComposeResult
from textual.containers import VerticalScroll

from titan_cli.core.logging import get_logger
from titan_cli.ui.components import error_card
from titan_cli.ui.tui.widgets.element_widgets import reconcile

from .base import BaseScreen

logger = get_logger(__name__)

GUTTER = 4  # the body's padding and its scrollbar


class WorkspaceScreen(BaseScreen):
    """The screen of the workspace called `workspace`; `title` heads it."""

    BINDINGS = [("escape", "go_back", "Back")]

    DEFAULT_CSS = """
    WorkspaceScreen #workspace-body {
        height: 1fr;
        padding: 0 1;
        scrollbar-gutter: stable;
    }
    """

    def __init__(self, config, workspace: str, title: str):
        super().__init__(config, title=title, show_back=True)
        self.workspace = workspace

    def compose_content(self) -> ComposeResult:
        yield VerticalScroll(id="workspace-body")

    def on_mount(self) -> None:
        # The size is known only after the first layout.
        self.call_after_refresh(self.refresh_view)

    def on_resize(self) -> None:
        self.refresh_view()

    def on_screen_resume(self) -> None:
        super().on_screen_resume()
        self.refresh_view()

    def refresh_view(self) -> None:
        """Draw the workspace's view again, patching what is on screen."""
        bus = getattr(self.app, "workspaces", None)
        if bus is None or self.workspace not in bus.views:
            return
        # A repaint can arrive between the screen being pushed and its body being composed:
        # on_mount draws the first time, so there is nothing to patch yet.
        bodies = self.query("#workspace-body")
        if not bodies:
            return
        body = bodies.first(VerticalScroll)
        width = max(10, (body.size.width or self.size.width) - GUTTER)
        try:
            tree = bus.render_view(self.workspace, width)
        except Exception as e:
            logger.exception("workspace_render_failed", workspace=self.workspace)
            host = self.app.mods_host
            tree = error_card(
                f"{type(e).__name__}: {e}",
                copy=lambda text, what: host.copy(bus.prefix + self.workspace, text, what),
                title=f"Workspace {self.workspace} failed to draw",
            )
        with self.app.batch_update():
            reconcile(body, [tree] if tree is not None else [], width)
