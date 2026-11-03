"""The cli workspace: a terminal for the active session, or the CLIs to start one; the widget's key rules."""
from pathlib import Path
from types import SimpleNamespace

import pytest

from titan_cli.cli_sessions import SESSIONS
from titan_cli.core.mods import WORKSPACES, ModBus, import_mod
from titan_cli.external_cli.launcher import CLILauncher
from titan_cli.ui.elements import Button, Component, Text, plain

FOLDER = Path(__file__).resolve().parents[3] / "titan_cli" / "workspaces" / "cli"
ws = import_mod(FOLDER, kind=WORKSPACES)
terminal = ws.terminal


@pytest.fixture(autouse=True)
def clean_registry():
    SESSIONS.sessions.clear()
    SESSIONS.active_id = None
    SESSIONS._listeners.clear()
    yield
    SESSIONS.sessions.clear()
    SESSIONS.active_id = None
    SESSIONS._listeners.clear()


def walk(element):
    yield element
    for child in getattr(element, "children", ()) or ():
        if child:
            yield from walk(child)


def start(monkeypatch, *installed, **options):
    monkeypatch.setattr(CLILauncher, "is_available", lambda self: self.cli_name in installed)
    dock = []
    host = SimpleNamespace(
        run=lambda mod, fn: fn(), client=lambda name: None, every=lambda *a: None, repaint=lambda mod: None,
        copy=lambda *a: None, toast=lambda *a: None, dock=lambda mod, slot: dock.append(slot),
        bind_key=lambda *a: None, resolve_workflow=lambda mod, name: name,
    )
    bus = ModBus(prefix="workspace.", store_dir="workspaces")
    bus.host = host
    w = bus.api("cli")
    ws.register(w, bus.on_for("cli"), {"memory_limit_mb": 512, **options})
    bus.start()
    return bus, w, dock


def buttons(bus):
    return [e for e in walk(bus.render_view("cli", 100)) if isinstance(e, Button)]


def terminal_props(bus):
    found = [e for e in walk(bus.render_view("cli", 100)) if isinstance(e, Component)]
    return found[0].props if found else None


def test_with_no_session_it_offers_the_clis_titan_finds_installed(monkeypatch):
    bus, w, dock = start(monkeypatch, "codex", "claude")
    assert [slot.label for slot in dock] == ["CLI"]
    assert [plain(b.label) for b in buttons(bus)] == ["▶ Claude CLI", "▶ Codex CLI"]
    assert terminal_props(bus) is None


def test_with_none_installed_it_says_so(monkeypatch):
    bus, _, _ = start(monkeypatch)
    tree = bus.render_view("cli", 100)
    assert not buttons(bus)
    assert any("No supported CLI" in plain(e) for e in walk(tree) if isinstance(e, Text))


def test_pressing_a_cli_starts_a_session_and_the_screen_becomes_its_terminal(monkeypatch):
    bus, w, _ = start(monkeypatch, "codex")
    next(b for b in buttons(bus) if "Codex" in plain(b.label)).on_press()
    props = terminal_props(bus)
    assert props.session.command == "codex" and props.session.memory_limit_mb == 512
    assert not buttons(bus)  # the whole screen is the terminal: the menu is the mod's


def test_a_session_started_elsewhere_shows_its_terminal(monkeypatch):
    bus, w, _ = start(monkeypatch, "codex")
    session = SESSIONS.launch("claude", "Claude CLI")
    assert terminal_props(bus).session is session


def test_leaving_and_opening_the_screen_again_shows_the_same_session(monkeypatch):
    bus, w, _ = start(monkeypatch, "codex")
    session = SESSIONS.launch("codex", "Codex CLI")
    bus.opened("cli", None)
    assert terminal_props(bus).session is session


def test_the_memory_limit_option_is_what_new_sessions_get(monkeypatch):
    start(monkeypatch, "codex", memory_limit_mb=1024)
    assert SESSIONS.launch("codex", "Codex CLI").memory_limit_mb == 1024


def test_the_line_the_cursor_left_is_redrawn_too():
    assert terminal.rows_to_redraw({2}, 5, 7) == {2, 5, 7}


def test_the_widget_overrides_no_private_method_of_textuals_own():
    from textual.widgets import Static

    mine = {name for name, value in vars(terminal.CliTerminal).items()
            if callable(value) and name.startswith("_") and not name.startswith("__")}
    assert {name for name in mine if hasattr(Static, name)} == set()


def test_the_terminal_keeps_the_keys_titan_binds_but_leaves_it_the_function_keys():
    widget = terminal.CliTerminal.__new__(terminal.CliTerminal)
    for key, character in (("q", "q"), ("u", "u"), ("ctrl+c", None), ("question_mark", "?"), ("escape", None)):
        assert widget.check_consume_key(key, character), key
    for key in ("f2", "f4", "f6"):
        assert not widget.check_consume_key(key, None), key
