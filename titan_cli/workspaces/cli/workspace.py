"""A dock tile that opens a full-screen terminal for the active CLI session; the menu is the `cli` mod's."""
from titan_cli.cli_sessions import SESSIONS, installed
from titan_cli.ui.components import Option, choice_card
from titan_cli.ui.elements import Box, Component, Text
from titan_cli.ui.tui.widgets.registry import register_widget

from .terminal import CliProps, CliTerminal

TITLE = "CLI"
WIDGET = "cli.terminal"


def register(w, on, options):
    register_widget(WIDGET, CliTerminal)
    SESSIONS.memory_limit_mb = int(options.get("memory_limit_mb", SESSIONS.memory_limit_mb))
    w.state.set("installed", [])
    SESSIONS.subscribe("workspace.cli", lambda: w.state.update("changes", lambda n: (n or 0) + 1, default=0))

    def view(width):
        current = SESSIONS.active()
        if current is not None:
            return Box(Component(WIDGET, CliProps(current)))
        found = w.state.get("installed") or []
        return Box(
            choice_card(
                [Option(f"▶ {label}", lambda c=name, lbl=label: SESSIONS.launch(c, lbl), "primary") for name, label in found],
                width=width - 4,
                title="Start a CLI" if found else "No supported CLI found on PATH",
            ),
            Text("Sessions are listed in the CLI side panel; ctrl+] leaves the terminal and keeps them running.", dim=True),
        )

    w.ui.view(view, title=TITLE)

    def start(w):
        w.state.set("installed", installed())
        w.ui.dock(TITLE, on_click=w.ui.open_workspace)

    w.on_start(start)
    w.on_open(lambda w, focus: w.state.set("installed", installed()))
