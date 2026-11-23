"""
cli: a side pane with the CLI sessions - which are running, which one is on screen - and the ways to start,
switch to and close one. The terminal is the `cli` workspace's, one press away: starting or choosing a
session opens it.

Sessions and what Titan knows about installed CLIs come from `titan_cli.cli_sessions`; drawing reads only
`m.state`, so it never waits. See docs/concepts/writing-mods.md.
"""
from titan_cli.cli_sessions import SESSIONS, installed
from titan_cli.ui.components import Option, choice_card
from titan_cli.ui.elements import Box, Button

PANE = "cli"
TITLE = "CLI"
MENU = "cli_menu"


def register(on, options):
    @on("app.start")
    def start(m, e, next):
        m.ui.open(PANE, TITLE)
        m.state.set("installed", installed())
        SESSIONS.subscribe("mod.cli", lambda: m.state.update("changes", lambda n: (n or 0) + 1, default=0))
        m.clock.every(options["installed_refresh_seconds"], lambda: m.state.set("installed", installed()))
        return next(e)

    @on("ui.render", match={"component": "Pane", "pane": PANE})
    def render(m, e, next):
        return draw(m, e.width)


def draw(m, width: int):
    """The pane: the sessions and what can be done with them, from `SESSIONS` and `m.state` only."""
    found = m.state.get("installed") or []

    def go(action):
        def press():
            action()
            m.ui.open_workspace("cli")
        return press

    starts = [Option(f"▶ {label}", go(lambda c=name, lbl=label: SESSIONS.launch(c, lbl)), "primary") for name, label in found]
    current = SESSIONS.active()
    if current is None:
        return Box(
            choice_card(starts, width=width, title="Start a CLI" if found else "No supported CLI found on PATH"),
        )
    confirming = m.state.get("confirm_close") == current.id
    picks = [
        Option(f"{'●' if s is current else '○'} {s.label}{' · exited' if s.exited else ''}",
               go(lambda sid=s.id: (m.state.set("confirm_close", None), SESSIONS.select(sid))),
               "primary" if s is current else "default")
        for s in SESSIONS.sessions
    ]
    tail = (
        [Option("✓ Confirm close", lambda: (m.state.set("confirm_close", None), SESSIONS.close()), "error"),
         Option("Cancel", lambda: m.state.set("confirm_close", None))]
        if confirming else [Option("✗ Close this session", lambda: m.state.set("confirm_close", current.id))]
    )
    return Box(
        choice_card(
            [*picks, Option("＋ New session", options=starts) if starts else None, *tail],
            width=width,
            title="CLI sessions",
            hint="Closing stops the CLI and loses its conversation." if confirming else "",
            state=m.state,
            key=MENU,
            border="warning" if confirming else "subtle",
        ),
        Button("↗ Open terminal", lambda: m.ui.open_workspace("cli")),
    )
