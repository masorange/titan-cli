"""
`CliTerminal`: the widget that shows a `Session` (see `titan_cli.cli_sessions`).

It attaches to a session, draws its screen and forwards keys and pastes. The mouse wheel goes to the CLI
when it asked for mouse reports, becomes arrow keys on its alternate screen, and otherwise scrolls the
session's scrollback (as do shift+pageup/pagedown); typing returns to the live screen. Unmounting it stops
nothing: the session lives apart, so leaving the workspace and coming back finds it as it was.
"""
from dataclasses import dataclass
from typing import List, Optional

from rich.text import Text as RichText
from textual.events import Key, MouseScrollDown, MouseScrollUp, Paste, Resize
from textual.widgets import Static

from titan_cli.cli_sessions import (
    Session, key_bytes, paste_bytes, render_line, render_row, scrollback_window, wheel_bytes,
)
from titan_cli.ui.tui.widgets.error_card import ErrorCard

EXIT_KEY = "ctrl+right_square_bracket"
SCROLL_KEYS = {"shift+pageup": True, "shift+pagedown": False}  # key: scrolls up
WHEEL_STEP = 3  # rows per wheel notch

@dataclass(frozen=True)
class CliProps:
    """What the widget shows: a session."""

    session: Session


def rows_to_redraw(dirty, previous_cursor_y: int, cursor_y: int) -> set:
    """pyte marks a line dirty when it is drawn on, not when the cursor leaves it: redraw both."""
    return {*dirty, previous_cursor_y, cursor_y}


class CliTerminal(Static, can_focus=True):
    """Draws a `Session`'s screen and forwards keys and pastes to it. Unmounting stops nothing."""

    DEFAULT_CSS = """
    CliTerminal { height: 1fr; width: 1fr; background: black; border: round $primary-darken-2; }
    CliTerminal:focus { border: round $primary; }
    """

    def __init__(self, props: CliProps) -> None:
        super().__init__("", markup=False)
        self._props = props
        self._session: Optional[Session] = None
        self._lines: List[RichText] = []
        self._seen = -1
        self._cursor_y = 0
        self._offset = 0  # rows scrolled back into the scrollback; 0 is the live screen

    # -- Updatable ------------------------------------------------------------------------
    def apply(self, props: CliProps) -> None:
        self._props = props
        if props.session is not self._session:
            self._bind_session(props.session)
            self.focus()
        self.call_after_refresh(self._fit)

    def _fit(self) -> None:
        """Take the rest of the workspace body under whatever is above, down to the dock."""
        try:
            body = self.screen.query_one("#workspace-body")
        except Exception:
            return
        height = body.size.height - (self.region.y - body.region.y + int(body.scroll_y))
        if height >= 7 and self.styles.height != height:
            self.styles.height = height

    def _bind_session(self, session: Session) -> None:
        self._session = session
        self._lines, self._seen, self._offset = [], -1, 0
        self._sync_size()

    def on_mount(self) -> None:
        self.focus()
        self._bind_session(self._props.session)
        self.call_after_refresh(self._fit)
        self.set_interval(0.05, self._tick)

    def on_resize(self, event: Resize) -> None:
        self._sync_size()

    def _sync_size(self) -> None:
        session = self._session
        cols, rows = self.size.width - 2, self.size.height - 2
        if session is None or cols < 20 or rows < 5:
            return
        if session.started:
            session.resize(cols, rows)
        elif not session.exited:
            try:
                session.start(cols, rows)
            except OSError as e:
                self._show_launch_error(session, e)
                return
        self._lines, self._seen = [], -1

    def _show_launch_error(self, session: Session, error: Exception) -> None:
        """The CLI could not be launched: mark the session ended and say why in an error card."""
        session.exited = True
        self.display = False
        if self.parent is not None:
            self.parent.mount(ErrorCard(error, f"Could not start {session.label}"), before=self)

    # -- input ----------------------------------------------------------------------------
    def check_consume_key(self, key: str, character: Optional[str]) -> bool:
        """Every key the CLI can be sent is the CLI's, so Titan's own bindings (`q`, `ctrl+c`, `?`) do not fire.

        Without this the app's priority bindings run before the key reaches the widget. Keys that have no
        bytes to send (the F keys) stay Titan's.
        """
        return key in SCROLL_KEYS or key_bytes(key, character) is not None

    def on_key(self, event: Key) -> None:
        event.stop()
        if event.key == EXIT_KEY:
            self.screen.action_go_back()
        elif event.key in SCROLL_KEYS:
            self._scroll_back(SCROLL_KEYS[event.key], max(self.size.height - 3, 1))
        elif self._session is not None:
            self._scroll_to_live()
            self._session.send(key_bytes(event.key, event.character) or b"")

    def on_mouse_scroll_up(self, event: MouseScrollUp) -> None:
        self._wheel(event, up=True)

    def on_mouse_scroll_down(self, event: MouseScrollDown) -> None:
        self._wheel(event, up=False)

    def _wheel(self, event, up: bool) -> None:
        """The CLI's when it reads the mouse or is full-screen; otherwise a scroll through the scrollback."""
        event.stop()
        event.prevent_default()
        session = self._session
        if session is None:
            return
        with session.lock:
            screen = session.screen
            tracking, sgr, alternate = screen.mouse_tracking, screen.sgr_mouse, screen.alternate
        if tracking and not session.exited:
            col = min(max(event.x, 1), screen.columns)  # the border takes column and row 0
            row = min(max(event.y, 1), screen.lines)
            session.send(wheel_bytes(up, col, row, sgr))
        elif alternate and not session.exited:
            session.send(key_bytes("up" if up else "down", None) * WHEEL_STEP)
        else:
            self._scroll_back(up, WHEEL_STEP)

    def _scroll_back(self, up: bool, rows: int) -> None:
        session = self._session
        if session is None:
            return
        with session.lock:
            available = 0 if session.screen.alternate else len(session.screen.history)
        offset = min(max(self._offset + (rows if up else -rows), 0), available)
        if offset != self._offset:
            self._offset = offset
            self._seen = -1

    def _scroll_to_live(self) -> None:
        if self._offset:
            self._offset, self._seen = 0, -1

    def on_paste(self, event: Paste) -> None:
        """Textual delivers a paste as its own event, not as keys: hand it to the CLI."""
        event.stop()
        if self._session is not None:
            self._session.send(paste_bytes(event.text, self._session.bracketed))

    # -- drawing --------------------------------------------------------------------------
    def _tick(self) -> None:
        session = self._session
        if session is None:
            return
        if self._offset:
            if session.version != self._seen:
                self._draw_scrolled(session)
        elif session.version != self._seen or not self._lines:
            with session.lock:
                screen = session.screen
                if len(self._lines) != screen.lines:
                    self._lines = [render_line(screen, y) for y in range(screen.lines)]
                else:
                    for y in rows_to_redraw(screen.dirty, self._cursor_y, screen.cursor.y):
                        if 0 <= y < len(self._lines):
                            self._lines[y] = render_line(screen, y)
                screen.dirty.clear()
                self._cursor_y = screen.cursor.y
                self._seen = session.version
            self.update(RichText("\n").join(self._lines))
        status = session.status()
        if self._offset:
            status += f" · scrolled back {self._offset} lines, type to return"
        self.border_title = status

    def _draw_scrolled(self, session: Session) -> None:
        """The view `_offset` rows back: the end of the scrollback, then the top of the screen."""
        with session.lock:
            screen, history = session.screen, session.screen.history
            self._offset = min(self._offset, len(history))
            rows = []
            for i in scrollback_window(len(history), screen.lines, self._offset):
                row = history[i] if i < len(history) else screen.buffer[i - len(history)]
                rows.append(render_row(row, screen.columns))
            self._seen = session.version
        self._lines = []  # the live view is drawn again in full on return
        self.update(RichText("\n").join(rows))
