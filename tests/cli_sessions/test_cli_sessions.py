"""CLI sessions: the emulation (what pyte sees, what is answered), the PTY sessions and their memory cap, and the registry."""
import os
import subprocess
import sys
import time

import pyte
import pytest

from titan_cli.cli_sessions import SessionRegistry, emulation, installed
from titan_cli.cli_sessions import session as session_mod
from titan_cli.external_cli.launcher import CLILauncher


def test_keys_become_terminal_bytes():
    assert emulation.key_bytes("enter", "\r") == b"\r"
    assert emulation.key_bytes("up", None) == b"\x1b[A"
    assert emulation.key_bytes("ctrl+c", None) == b"\x03"
    assert emulation.key_bytes("a", "a") == b"a"
    assert emulation.key_bytes("f5", None) is None


def test_a_screen_row_is_one_text_with_styled_runs():
    screen = pyte.Screen(20, 2)
    pyte.ByteStream(screen).feed(b"\x1b[1;31mhi\x1b[0m there")
    line = emulation.render_line(screen, 0)
    assert line.plain.rstrip() == "hi there"
    assert any(span.style and span.style.bold for span in line.spans)


def test_tree_rss_counts_the_process_and_its_children():
    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(5)"])
    try:
        time.sleep(0.3)
        assert session_mod.tree_rss_mb(os.getpid()) > session_mod.tree_rss_mb(child.pid) > 0
    finally:
        child.kill()


def test_tree_rss_falls_back_to_ps_when_proc_is_missing(monkeypatch):
    monkeypatch.setattr(session_mod.os.path, "isdir", lambda p: False if p == "/proc" else os.path.isdir(p))
    assert session_mod.tree_rss_mb(os.getpid()) > 0


def test_tree_rss_is_none_when_nothing_can_be_read(monkeypatch):
    def broken():
        raise FileNotFoundError("no ps")
    monkeypatch.setattr(session_mod, "_proc_table", broken)
    assert session_mod.tree_rss_mb(os.getpid()) is None


@pytest.fixture(autouse=True)
def fresh_scope_probe():
    session_mod.reset_scope_probe()
    yield
    session_mod.reset_scope_probe()


def test_without_systemd_the_command_runs_unwrapped(monkeypatch):
    monkeypatch.setattr(session_mod.shutil, "which", lambda name: None)
    assert session_mod.probe_scope() is False
    assert session_mod.wrap_in_scope(("codex",), 512) == (("codex",), False)


def test_a_hung_systemd_probe_means_unwrapped_not_a_crash(monkeypatch):
    monkeypatch.setattr(session_mod.shutil, "which", lambda name: "/usr/bin/systemd-run")

    def hang(*a, **k):
        raise subprocess.TimeoutExpired("systemd-run", 5)
    monkeypatch.setattr(session_mod.subprocess, "run", hang)
    assert session_mod.probe_scope() is False
    assert session_mod.wrap_in_scope(("codex",), 512) == (("codex",), False)


def test_the_probe_runs_once_and_wrapping_never_waits_for_it(monkeypatch):
    calls = []
    monkeypatch.setattr(session_mod.shutil, "which", lambda name: "/usr/bin/systemd-run")

    def slow(*a, **k):
        calls.append(1)
        time.sleep(0.3)
        return subprocess.CompletedProcess(a, 0)
    monkeypatch.setattr(session_mod.subprocess, "run", slow)
    started = time.time()
    assert session_mod.wrap_in_scope(("codex",), 512) == (("codex",), False)  # not ready: unwrapped, at once
    assert time.time() - started < 0.2
    deadline = time.time() + 5
    while time.time() < deadline and session_mod._scope_state is None:
        time.sleep(0.05)
    argv, scoped = session_mod.wrap_in_scope(("codex",), 512)
    assert scoped and argv[-1] == "codex"
    session_mod.wrap_in_scope(("codex",), 512)
    assert len(calls) == 1


def test_the_scope_caps_memory_and_kills_the_hog():
    hog = ("python3", "-c", "x=[]\nfor _ in range(40):\n x.append(bytearray(100<<20)); x[-1][::4096]=b'1'*len(x[-1][::4096])")
    session_mod.probe_scope()
    argv, scoped = session_mod.wrap_in_scope(hog, 300)
    if not scoped:
        pytest.skip("no systemd user scope here")
    assert subprocess.run(argv, capture_output=True, timeout=60).returncode == -9


def wait_for(session, condition, seconds=5):
    deadline = time.time() + seconds
    while time.time() < deadline and not condition(session):
        time.sleep(0.05)


def test_a_session_keeps_its_screen_with_no_widget_on_screen():
    session = session_mod.Session(1, "sh", "Shell", "/tmp", 512)
    session.start(40, 5)
    try:
        wait_for(session, lambda s: any(line.startswith("$") for line in s.screen.display))  # the prompt
        session.send(b"echo kept; sleep 30\r")
        wait_for(session, lambda s: any(line.startswith("kept") for line in s.screen.display))
        assert any(line.startswith("kept") for line in session.screen.display)
        assert not session.exited
    finally:
        session.stop(now=True)
    wait_for(session, lambda s: s.exited)
    assert session.exited
    assert subprocess.run(["pgrep", "-f", "^sleep 30$"], capture_output=True).returncode == 1  # its children too


def test_a_missing_command_or_folder_fails_before_forking():
    missing = session_mod.Session(1, "titan-no-such-cli", "Nope", "/tmp", 512)
    with pytest.raises(FileNotFoundError):
        missing.start(80, 24)
    assert not missing.started
    nowhere = session_mod.Session(2, "echo", "Echo", "/titan/no/such/folder", 512)
    with pytest.raises(FileNotFoundError):
        nowhere.start(80, 24)
    assert not nowhere.started


def test_a_session_whose_cli_ends_is_marked_exited():
    session = session_mod.Session(1, "true", "True", "/tmp", 512)
    session.start(40, 5)
    deadline = time.time() + 5
    while time.time() < deadline and not session.exited:
        time.sleep(0.1)
    assert session.exited and session.status() == "True · exited"


def test_resizing_an_exited_session_resizes_the_screen_but_touches_no_descriptor(monkeypatch):
    session = session_mod.Session(1, "true", "True", "/tmp", 512)
    session.start(40, 5)
    wait_for(session, lambda s: s.exited and s._fd is None)
    assert session.exited and session._fd is None and session.started
    calls = []
    monkeypatch.setattr(session_mod.fcntl, "ioctl", lambda *a: calls.append(a))
    monkeypatch.setattr(session_mod.os, "killpg", lambda *a: calls.append(a))
    session.resize(60, 10)
    assert (session.screen.columns, session.screen.lines) == (60, 10)
    assert calls == []


def test_a_failing_window_size_call_does_not_raise():
    session = session_mod.Session(1, "sh", "Shell", "/tmp", 512)
    read_end, write_end = os.pipe()
    os.close(read_end)
    os.close(write_end)
    session._fd = read_end  # closed descriptor: ioctl fails with EBADF
    session._winsize(80, 24)


def test_ensure_cap_never_touches_titans_own_cgroup():
    assert session_mod.ensure_cap(os.getpid(), 512) is False


def test_a_private_prefixed_sgr_does_not_underline_the_screen():
    screen = pyte.Screen(20, 2)
    stream, clean = pyte.ByteStream(screen), emulation.Sanitizer()
    stream.feed(clean.feed(b"\x1b[>4;1mhello"))
    assert not any(ch.underscore or ch.bold for ch in screen.buffer[0].values())


def test_a_sequence_split_across_reads_is_still_removed():
    clean = emulation.Sanitizer()
    out = clean.feed(b"ab\x1b[>4") + clean.feed(b";1mcd")
    assert out == b"abcd"


def test_a_plain_sgr_and_text_pass_through():
    assert emulation.Sanitizer().feed(b"\x1b[1;31mhi\x1b[0m") == b"\x1b[1;31mhi\x1b[0m"


def test_what_gemini_sends_at_start_does_not_break_the_parser():
    screen = pyte.Screen(40, 3)
    stream, clean = pyte.ByteStream(screen), emulation.Sanitizer()
    stream.feed(clean.feed(b"\x1b[8m\x1b[?u\x1b]11;?\x1b\\\x1b[>q\x1b[>4;?m\x1b[c\x1b[2K\r\x1b[0mok"))
    assert screen.display[0].startswith("ok")


def test_private_modes_pyte_implements_still_pass():
    assert emulation.Sanitizer().feed(b"\x1b[?25l\x1b[?1049h") == b"\x1b[?25l\x1b[?1049h"


def test_a_paste_is_bracketed_only_when_the_cli_asked_for_it():
    assert emulation.paste_bytes("code", True) == b"\x1b[200~code\x1b[201~"
    assert emulation.paste_bytes("a\nb", False) == b"a\rb"


KITTY = b"a\x1b_Ga=d,d=i,i=1,q=2\x1b\\b\x1b_Gf=100;AAAA\x1b\\c"


def test_kitty_graphics_strings_are_not_drawn_as_text():
    assert emulation.Sanitizer().feed(KITTY) == b"abc"


def test_a_graphics_string_split_anywhere_is_still_removed():
    for cut in range(len(KITTY) + 1):
        clean = emulation.Sanitizer()
        assert clean.feed(KITTY[:cut]) + clean.feed(KITTY[cut:]) == b"abc", cut


def test_queries_get_a_reply_and_are_not_drawn():
    clean = emulation.Sanitizer()
    clean.rows, clean.cols = 30, 100
    out = clean.feed(b"\x1b[>q\x1b[?u\x1b]11;?\x07\x1b[?2026$p\x1b[18t\x1b]10;?\x1b\\x")
    assert out == b"x"
    assert clean.take_replies() == [
        b"\x1bP>|titan\x1b\\", b"\x1b[?0u", b"\x1b]11;rgb:0000/0000/0000\x07",
        b"\x1b[?2026;0$y", b"\x1b[8;30;100t", b"\x1b]10;rgb:cccc/cccc/cccc\x1b\\",
    ]
    assert clean.take_replies() == []


def test_sgr_sub_parameters_and_underline_colours_are_made_plain():
    clean = emulation.Sanitizer()
    assert clean.feed(b"\x1b[38:2::1:2:3m") == b"\x1b[38;2;1;2;3m"
    assert clean.feed(b"\x1b[4:3m") == b"\x1b[4m"
    assert clean.feed(b"\x1b[1;58;2;9;9;9;3m") == b"\x1b[1;3m"


def test_what_pyte_has_no_handler_for_is_dropped():
    assert emulation.Sanitizer().feed(b"a\x1b[5 qb\x1b[?1000$pc\x1b[1;2zd\x1bP1$r\x1b\\e") == b"abcde"


def test_no_stream_of_escapes_can_break_pyte_or_underline_the_screen():
    import random

    rng = random.Random(7)
    pieces = [b"\x1b", b"[", b"]", b"_", b"P", b"\\", b"\x07", b">", b"?", b"<", b"=", b";", b":", b"$",
              b" ", b"4", b"1", b"m", b"h", b"l", b"q", b"p", b"t", b"c", b"u", b"G", b"hello", b"\n", b"\xe2\x94\x80"]
    for _ in range(300):
        screen = pyte.Screen(40, 6)
        stream, clean = pyte.ByteStream(screen), emulation.Sanitizer()
        data = b"".join(rng.choice(pieces) for _ in range(rng.randint(1, 60)))
        cuts = sorted(rng.sample(range(len(data) + 1), min(3, len(data) + 1)))
        for a, b in zip([0] + cuts, cuts + [len(data)]):
            stream.feed(clean.feed(data[a:b]))


def emulate(data: bytes, cols=10, lines=4):
    screen = emulation.TermScreen(cols, lines)
    stream, clean = emulation.TermStream(screen), emulation.Sanitizer()
    stream.feed(clean.feed(data))
    return screen


def shown(screen):
    return [line.rstrip() for line in screen.display]


def test_scroll_up_and_down_move_the_lines_inside_the_margins():
    base = b"\x1b[1;1Haa\r\nbb\r\ncc\r\ndd"
    assert shown(emulate(base + b"\x1b[1S")) == ["bb", "cc", "dd", ""]
    assert shown(emulate(base + b"\x1b[1T")) == ["", "aa", "bb", "cc"]
    assert shown(emulate(base + b"\x1b[2;3r\x1b[1S")) == ["aa", "cc", "", "dd"]


def test_repeat_draws_the_last_character_again():
    assert shown(emulate(b"x\x1b[3b")) == ["xxxx", "", "", ""]


def test_save_and_restore_cursor_as_csi():
    assert shown(emulate(b"ab\x1b[s\r\ncd\x1b[uZ")) == ["abZ", "cd", "", ""]


def test_the_alternate_screen_is_left_as_the_main_one_was():
    screen = emulate(b"main\x1b[?1049hother\x1b[?1049l")
    assert shown(screen)[0] == "main"
    assert shown(emulate(b"main\x1b[?1049hother"))[0] == "other"


def test_a_wide_character_takes_two_cells_not_three():
    screen = emulate("a世b".encode(), cols=6, lines=1)
    assert emulation.render_line(screen, 0).cell_len == 6
    assert emulation.render_line(screen, 0).plain.startswith("a世b")


def test_a_recording_keeps_the_bytes_the_cli_sent(tmp_path, monkeypatch):
    monkeypatch.setenv("TITAN_CLI_RECORD", str(tmp_path))
    session = session_mod.Session(3, "echo", "Echo", "/tmp", 512)
    session.start(40, 5)
    wait_for(session, lambda s: s.exited)
    assert (tmp_path / "echo-3.bin").read_bytes().strip() == b""  # `echo` with no argument prints a newline


def registry():
    reg = SessionRegistry()
    reg.memory_limit_mb = 512
    return reg


def test_a_launched_session_is_the_active_one_and_a_repeat_is_numbered():
    reg = registry()
    first = reg.launch("codex", "Codex CLI")
    second = reg.launch("codex", "Codex CLI")
    assert [s.label for s in reg.sessions] == ["Codex CLI", "Codex CLI #2"]
    assert reg.active() is second and first.memory_limit_mb == 512 and not first.started


def test_selecting_switches_the_active_session():
    reg = registry()
    first = reg.launch("codex", "Codex CLI")
    reg.launch("claude", "Claude CLI")
    reg.select(first.id)
    assert reg.active() is first


def test_closing_stops_the_session_and_the_last_one_left_becomes_active():
    reg = registry()
    first = reg.launch("codex", "Codex CLI")
    second = reg.launch("claude", "Claude CLI")
    stopped = []
    second.stop = lambda: stopped.append(second.label)
    reg.close()
    assert stopped == ["Claude CLI"] and reg.sessions == [first] and reg.active() is first
    first.stop = lambda: None
    reg.close()
    assert reg.sessions == [] and reg.active() is None


def test_listeners_hear_every_change_and_a_key_again_replaces_its_listener():
    reg = registry()
    heard = []
    reg.subscribe("a", lambda: heard.append("old"))
    reg.subscribe("a", lambda: heard.append("a"))
    reg.subscribe("b", lambda: heard.append("b"))
    session = reg.launch("codex", "Codex CLI")
    session.stop = lambda: None
    reg.close()
    assert heard == ["a", "b", "a", "b"]


def test_an_exiting_session_tells_the_listeners():
    reg = registry()
    heard = []
    reg.subscribe("a", lambda: heard.append(1))
    session = reg.launch("true", "True")
    session.start(40, 5)
    wait_for(session, lambda s: s.exited)
    assert len(heard) == 2  # the launch, then the exit


def test_stop_all_ends_every_session_at_once():
    reg = registry()
    stopped = []
    for command in ("codex", "claude"):
        reg.launch(command, command).stop = lambda now=False, c=command: stopped.append((c, now))
    reg.stop_all()
    assert stopped == [("codex", True), ("claude", True)]


def test_installed_lists_the_registered_clis_that_are_on_the_path(monkeypatch):
    monkeypatch.setattr(CLILauncher, "is_available", lambda self: self.cli_name in ("codex", "claude"))
    assert installed() == [("claude", "Claude CLI"), ("codex", "Codex CLI")]

