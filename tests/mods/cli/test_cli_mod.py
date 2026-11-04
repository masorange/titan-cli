"""The cli mod: its pane lists the sessions and starts, switches and closes them; the terminal is the workspace's."""
from pathlib import Path
from types import SimpleNamespace

import pytest

from titan_cli.cli_sessions import SESSIONS
from titan_cli.core.mods import MODS, ModBus, import_mod
from titan_cli.ui.elements import Button, plain

FOLDER = Path(__file__).resolve().parents[3] / "titan_cli" / "mods" / "cli"
mod = import_mod(FOLDER, kind=MODS)


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


def pane(installed=(("codex", "Codex CLI"), ("claude", "Claude CLI"))):
    opened = []
    bus = ModBus()
    bus.host = SimpleNamespace(repaint=lambda mod_: None, open_workspace=lambda mod_, name, focus=None: opened.append(name))
    m = bus.api("cli")
    m.state.set("installed", list(installed))
    return m, opened


def buttons(m):
    return {plain(b.label): b for b in walk(mod.draw(m, 44)) if isinstance(b, Button)}


def test_with_no_session_the_pane_offers_the_installed_clis():
    m, _ = pane()
    assert list(buttons(m)) == ["▶ Codex CLI", "▶ Claude CLI"]


def test_with_none_installed_the_pane_says_so():
    m, _ = pane(installed=())
    assert not buttons(m)


def test_starting_a_cli_makes_a_session_and_opens_the_workspace():
    m, opened = pane()
    buttons(m)["▶ Codex CLI"].on_press()
    assert [s.label for s in SESSIONS.sessions] == ["Codex CLI"] and opened == ["cli"]


def test_with_sessions_the_pane_marks_the_active_one_and_offers_new_session_and_close():
    m, _ = pane()
    SESSIONS.launch("codex", "Codex CLI")
    SESSIONS.launch("claude", "Claude CLI")
    labels = list(buttons(m))
    assert "○ Codex CLI" in labels and "● Claude CLI" in labels
    assert "▸ ＋ New session" in labels and "✗ Close this session" in labels and "↗ Open terminal" in labels


def test_choosing_a_session_switches_to_it_and_opens_the_workspace():
    m, opened = pane()
    SESSIONS.launch("codex", "Codex CLI")
    SESSIONS.launch("claude", "Claude CLI")
    buttons(m)["○ Codex CLI"].on_press()
    assert SESSIONS.active().command == "codex" and opened == ["cli"]


def test_a_new_session_comes_from_the_dropdown():
    m, opened = pane()
    SESSIONS.launch("codex", "Codex CLI")
    m.state.set("cli_menu", "＋ New session")
    buttons(m)["▶ Claude CLI"].on_press()
    assert [s.label for s in SESSIONS.sessions] == ["Codex CLI", "Claude CLI"] and opened == ["cli"]


def test_closing_asks_first_then_stops_the_session():
    m, _ = pane()
    session = SESSIONS.launch("codex", "Codex CLI")
    stopped = []
    session.stop = lambda: stopped.append(1)
    buttons(m)["✗ Close this session"].on_press()
    assert stopped == [] and "✓ Confirm close" in buttons(m)
    buttons(m)["✓ Confirm close"].on_press()
    assert stopped == [1] and SESSIONS.sessions == []


def test_cancel_keeps_the_session():
    m, _ = pane()
    SESSIONS.launch("codex", "Codex CLI")
    buttons(m)["✗ Close this session"].on_press()
    buttons(m)["Cancel"].on_press()
    assert "✗ Close this session" in buttons(m) and len(SESSIONS.sessions) == 1


def test_the_press_into_the_workspace_is_there_for_the_active_session():
    m, opened = pane()
    SESSIONS.launch("codex", "Codex CLI")
    buttons(m)["↗ Open terminal"].on_press()
    assert opened == ["cli"]
