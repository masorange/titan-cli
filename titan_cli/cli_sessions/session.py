"""
`Session`: one CLI running in a PTY, kept current by its own threads whether or not a widget shows it.

Memory is bounded on our side: no scrollback (pyte `Screen`, not `HistoryScreen`). The child's own memory
is watched (`tree_rss_mb`) and capped twice: by the cgroup it really runs in (`MemoryMax`,
`MemorySwapMax=0`, see `ensure_cap`) and by a watchdog that kills the process group past the limit.
"""
import fcntl
import os
import pty
import shutil
import signal
import struct
import subprocess
import termios
import threading
import time
from typing import Callable, Optional, Tuple

from titan_cli.core.logging import get_logger

from .emulation import Sanitizer, TermScreen, TermStream

logger = get_logger(__name__)


def tree_rss_mb(pid: int) -> float:
    """Resident memory of a process and all its descendants, in MB, read from /proc."""
    page = os.sysconf("SC_PAGE_SIZE")
    parents = {}
    for name in os.listdir("/proc"):
        if not name.isdigit():
            continue
        try:
            with open(f"/proc/{name}/stat") as f:
                parents[int(name)] = int(f.read().rsplit(")", 1)[1].split()[1])
        except (OSError, ValueError, IndexError):
            continue
    family, grew = {pid}, True
    while grew:
        grew = False
        for child, parent in parents.items():
            if parent in family and child not in family:
                family.add(child)
                grew = True
    total = 0
    for p in family:
        try:
            with open(f"/proc/{p}/statm") as f:
                total += int(f.read().split()[1]) * page
        except (OSError, ValueError, IndexError):
            continue
    return total / 1024 / 1024


def wrap_in_scope(argv: Tuple[str, ...], memory_limit_mb: int) -> Tuple[Tuple[str, ...], bool]:
    """`argv` under a user systemd scope capped at the limit; unchanged when that is unavailable."""
    if not shutil.which("systemd-run"):
        return argv, False
    probe = subprocess.run(["systemd-run", "--user", "--scope", "--quiet", "true"],
                           capture_output=True, timeout=10)
    if probe.returncode != 0:
        return argv, False
    return ("systemd-run", "--user", "--scope", "--quiet", "-p", f"MemoryMax={memory_limit_mb}M",
            "-p", "MemorySwapMax=0", "--", *argv), True


def _cgroup_dir(pid: int) -> Optional[str]:
    try:
        with open(f"/proc/{pid}/cgroup") as f:
            return "/sys/fs/cgroup" + f.read().strip().split("::", 1)[1]
    except (OSError, IndexError):
        return None


def kill_scope(pid: int) -> None:
    """SIGKILL every process of the unit `pid` runs in, children in other process groups included."""
    path, own = _cgroup_dir(pid), _cgroup_dir(os.getpid())
    if path and path != own:
        subprocess.run(["systemctl", "--user", "kill", "--signal=SIGKILL", os.path.basename(path)],
                       capture_output=True, timeout=10)


def ensure_cap(pid: int, memory_limit_mb: int) -> bool:
    """
    Make the cgroup the process really runs in carry the memory cap, and say whether it does.

    A launcher may move the CLI out of the scope we made (snap's `node` does), so the cap is
    read back from where the process is and, when it is not there, set on that unit. Titan's own
    cgroup is never touched.
    """
    path, own = _cgroup_dir(pid), _cgroup_dir(os.getpid())
    if not path or path == own or not os.path.isdir(path):
        return False
    want = memory_limit_mb * 1024 * 1024

    def current() -> Optional[int]:
        try:
            with open(f"{path}/memory.max") as f:
                text = f.read().strip()
            return None if text == "max" else int(text)
        except (OSError, ValueError):
            return None

    if current() != want:
        subprocess.run(["systemctl", "--user", "set-property", "--runtime", os.path.basename(path),
                        f"MemoryMax={memory_limit_mb}M", "MemorySwapMax=0"], capture_output=True, timeout=10)
    return current() == want


class Session:
    """One CLI running in a PTY, kept current by its own threads whether or not it is on screen."""

    def __init__(self, sid: int, command: str, label: str, cwd: str, memory_limit_mb: int) -> None:
        self.id, self.command, self.label = sid, command, label
        self.cwd, self.memory_limit_mb = cwd, memory_limit_mb
        self.screen = TermScreen(80, 24)
        self.lock = threading.Lock()  # guards the screen and the sanitizer
        self.version = 0  # bumped on every change of the screen
        self.exited = False
        self.on_exit: Optional[Callable[[], None]] = None  # called from the reader thread when the CLI ends
        self.bracketed = False
        self.rss = 0.0
        self.peak = 0.0
        self._stream = TermStream(self.screen)
        self._sanitizer = Sanitizer()
        self._fd: Optional[int] = None
        self._pid: Optional[int] = None
        self._scoped = False
        self._capped = False
        self._killed = False
        self._closing = threading.Event()
        # TITAN_CLI_RECORD=<folder>: keep the raw bytes each CLI sent, to replay a screen that looks wrong
        folder = os.environ.get("TITAN_CLI_RECORD")
        self._record = open(os.path.join(folder, f"{command}-{sid}.bin"), "wb") if folder else None
        self.screen.write_process_input = lambda data: self.send(data.encode())

    @property
    def started(self) -> bool:
        return self._pid is not None

    def start(self, cols: int, rows: int) -> None:
        argv, self._scoped = wrap_in_scope((self.command,), self.memory_limit_mb)
        self._apply_size(cols, rows)
        pid, fd = pty.fork()
        if pid == 0:
            os.chdir(self.cwd)
            os.execvpe(argv[0], list(argv), {**os.environ, "TERM": "xterm-256color", "COLORTERM": "truecolor"})
        self._pid, self._fd = pid, fd
        self._winsize(cols, rows)
        threading.Thread(target=self._read, args=(pid, fd), daemon=True).start()
        threading.Thread(target=self._watch, daemon=True).start()

    def resize(self, cols: int, rows: int) -> None:
        if (cols, rows) != (self.screen.columns, self.screen.lines):
            self._apply_size(cols, rows)
            self._winsize(cols, rows)

    def send(self, data: bytes) -> None:
        if data and self._fd is not None and not self.exited:
            try:
                os.write(self._fd, data)
            except OSError:
                pass

    def stop(self, now: bool = False) -> None:
        """Ask the CLI to end; whatever is left after two seconds (or at once, `now`) is killed."""
        pid = self._pid
        if pid is None or self.exited:
            return
        self._kill(signal.SIGTERM)
        if now:
            self._finish(pid)
        else:
            threading.Thread(target=self._finish, args=(pid,), kwargs={"wait": 2.0}, daemon=True).start()

    def _finish(self, pid: int, wait: float = 0.0) -> None:
        deadline = time.time() + wait
        while time.time() < deadline and not self.exited:
            time.sleep(0.05)
        if self.exited:
            return
        self._kill(signal.SIGKILL)
        if self._scoped:
            kill_scope(pid)

    def status(self) -> str:
        if self.exited:
            return f"{self.label} · exited"
        how = "cgroup cap" if self._capped else "watchdog only"
        return f"{self.label} · {self.rss:.0f} MB (peak {self.peak:.0f}) / {self.memory_limit_mb} MB [{how}] · ctrl+] leaves"

    # -- threads --------------------------------------------------------------------------
    def _read(self, pid: int, fd: int) -> None:
        while True:
            try:
                data = os.read(fd, 65536)
            except OSError:
                data = b""
            if not data:
                break
            if self._record is not None:
                self._record.write(data)
                self._record.flush()
            if b"\x1b[?2004h" in data:
                self.bracketed = True
            elif b"\x1b[?2004l" in data:
                self.bracketed = False
            with self.lock:
                try:
                    self._stream.feed(self._sanitizer.feed(data))
                except Exception:  # a sequence pyte cannot parse must never take the screen down
                    logger.warning("cli_terminal_unparsed_output", data=data[:80])
                replies = self._sanitizer.take_replies()
                self.version += 1
            for reply in replies:
                self.send(reply)
        self.exited = True
        self._closing.set()
        with self.lock:
            self.version += 1
        if self.on_exit:
            self.on_exit()
        try:
            os.waitpid(pid, 0)
        except OSError:
            pass
        try:
            os.close(fd)
        except OSError:
            pass

    def _watch(self) -> None:
        while not self._closing.wait(2.0):
            if self._scoped and not self._capped:
                self._capped = ensure_cap(self._pid, self.memory_limit_mb)
            self.rss = tree_rss_mb(self._pid)
            self.peak = max(self.peak, self.rss)
            if self.rss > self.memory_limit_mb and not self._killed:
                self._killed = True
                self._kill(signal.SIGKILL)

    # -- helpers --------------------------------------------------------------------------
    def _apply_size(self, cols: int, rows: int) -> None:
        with self.lock:
            self.screen.resize(rows, cols)
            self._sanitizer.rows, self._sanitizer.cols = rows, cols
            self.version += 1

    def _winsize(self, cols: int, rows: int) -> None:
        if self._fd is None:
            return
        fcntl.ioctl(self._fd, termios.TIOCSWINSZ, struct.pack("HHHH", rows, cols, 0, 0))
        self._kill(signal.SIGWINCH)

    def _kill(self, sig: int) -> None:
        if self._pid is None:
            return
        try:
            os.killpg(os.getpgid(self._pid), sig)
        except OSError:
            pass
