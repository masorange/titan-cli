"""
`Session`: one CLI running in a PTY, kept current by its own threads whether or not a widget shows it.

Memory is bounded on our side: the scrollback keeps at most `SCROLLBACK_LINES` rows. The child's own memory
is watched (`tree_rss_mb`: /proc, else `ps`) and capped twice: by the cgroup it really runs in (`MemoryMax`,
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
import queue
import threading
import time
from typing import Callable, Optional, Tuple

from titan_cli.core.logging import get_logger

from .emulation import Sanitizer, TermScreen, TermStream

logger = get_logger(__name__)


def _proc_table() -> dict:
    """`{pid: (ppid, rss_bytes)}` for every process, from /proc (Linux)."""
    page = os.sysconf("SC_PAGE_SIZE")
    table = {}
    for name in os.listdir("/proc"):
        if not name.isdigit():
            continue
        try:
            with open(f"/proc/{name}/stat") as f:
                ppid = int(f.read().rsplit(")", 1)[1].split()[1])
            with open(f"/proc/{name}/statm") as f:
                rss = int(f.read().split()[1]) * page
        except (OSError, ValueError, IndexError):
            continue
        table[int(name)] = (ppid, rss)
    return table


def _tool(name: str) -> str:
    """Absolute path of a system tool, so a subprocess never depends on a relative program name."""
    return shutil.which(name) or name


def _ps_table() -> dict:
    """`{pid: (ppid, rss_bytes)}` for every process, from `ps` (macOS and other systems without /proc)."""
    out = subprocess.run([_tool("ps"), "-A", "-o", "pid=,ppid=,rss="], capture_output=True, text=True, timeout=10).stdout
    table = {}
    for line in out.splitlines():
        try:
            pid, ppid, rss_kb = (int(x) for x in line.split())
        except ValueError:
            continue
        table[pid] = (ppid, rss_kb * 1024)
    return table


def tree_rss_mb(pid: int) -> Optional[float]:
    """
    Resident memory of a process and all its descendants, in MB: from /proc, else from `ps`.

    `None` when neither can be read, so the caller never shows 0 MB as if it were measured.
    """
    try:
        table = _proc_table() if os.path.isdir("/proc") else _ps_table()
    except (OSError, subprocess.SubprocessError):
        return None
    if not table:
        return None
    family, grew = {pid}, True
    while grew:
        grew = False
        for child, (parent, _) in table.items():
            if parent in family and child not in family:
                family.add(child)
                grew = True
    return sum(table[p][1] for p in family if p in table) / 1024 / 1024


_scope_lock = threading.Lock()
_scope_state: Optional[bool] = None  # None: not probed yet
_scope_warming = False


def probe_scope() -> bool:
    """Whether a user systemd scope can be made here. Blocks up to the probe timeout: never call it from the UI thread."""
    global _scope_state
    ok = False
    if shutil.which("systemd-run"):
        try:
            ok = subprocess.run([_tool("systemd-run"), "--user", "--scope", "--quiet", "true"],
                                capture_output=True, timeout=5).returncode == 0
        except (subprocess.TimeoutExpired, OSError):
            ok = False
    with _scope_lock:
        _scope_state = ok
    return ok


def warm_scope_probe() -> None:
    """Run the probe once in a daemon thread, so the UI thread never waits for it."""
    global _scope_warming
    with _scope_lock:
        if _scope_state is not None or _scope_warming:
            return
        _scope_warming = True

    def run() -> None:
        global _scope_warming
        try:
            probe_scope()
        finally:
            with _scope_lock:
                _scope_warming = False

    threading.Thread(target=run, daemon=True).start()


def reset_scope_probe() -> None:
    """Forget the cached probe result (tests that change what is installed)."""
    global _scope_state
    with _scope_lock:
        _scope_state = None


def wrap_in_scope(argv: Tuple[str, ...], memory_limit_mb: int) -> Tuple[Tuple[str, ...], bool]:
    """
    `argv` under a user systemd scope capped at the limit; unchanged when that is unavailable.

    Never blocks: it uses the cached probe, and when the probe has not finished yet the command runs unwrapped
    (the watchdog still applies).
    """
    with _scope_lock:
        available = _scope_state
    if available is None:
        warm_scope_probe()
        return argv, False
    if not available:
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
        subprocess.run([_tool("systemctl"), "--user", "kill", "--signal=SIGKILL", os.path.basename(path)],
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
        subprocess.run([_tool("systemctl"), "--user", "set-property", "--runtime", os.path.basename(path),
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
        self.rss = 0.0
        self.measured = True  # False once memory cannot be read on this system: no watchdog then
        self.peak = 0.0
        self._stream = TermStream(self.screen)
        self._sanitizer = Sanitizer()
        self._fd: Optional[int] = None
        self._pid: Optional[int] = None
        self._scoped = False
        self._capped = False
        self._killed = False
        self._closing = threading.Event()
        self._writes: "queue.Queue[Optional[bytes]]" = queue.Queue()  # input for the writer thread
        # TITAN_CLI_RECORD=<folder>: keep the raw bytes each CLI sent, to replay a screen that looks wrong
        folder = os.environ.get("TITAN_CLI_RECORD")
        self._record = open(os.path.join(folder, f"{os.path.basename(command)}-{int(sid)}.bin"), "wb") if folder else None
        self.screen.write_process_input = lambda data: self.send(data.encode())

    @property
    def started(self) -> bool:
        return self._pid is not None

    def start(self, cols: int, rows: int) -> None:
        """Fork the CLI into a PTY. Raises `FileNotFoundError` before forking when it cannot be launched."""
        executable = shutil.which(self.command)
        if not executable:
            raise FileNotFoundError(f"'{self.command}' was not found on the PATH")
        if not os.path.isdir(self.cwd):
            raise FileNotFoundError(f"The folder '{self.cwd}' does not exist")
        argv, self._scoped = wrap_in_scope((executable,), self.memory_limit_mb)
        if self._scoped:  # systemd-run is the program; the CLI is its resolved absolute-path argument
            executable = shutil.which(argv[0]) or argv[0]
        env = {**os.environ, "TERM": "xterm-256color", "COLORTERM": "truecolor"}
        self._apply_size(cols, rows)
        pid, fd = pty.fork()
        if pid == 0:
            # Whatever goes wrong here, this forked copy of Titan must never return into the app.
            try:
                os.chdir(self.cwd)
                os.execve(executable, list(argv), env)
            except BaseException:
                pass
            os._exit(127)
        self._pid, self._fd = pid, fd
        self._winsize(cols, rows)
        threading.Thread(target=self._read, args=(pid, fd), daemon=True).start()
        threading.Thread(target=self._watch, daemon=True).start()
        threading.Thread(target=self._write, daemon=True).start()

    @property
    def bracketed(self) -> bool:
        """Whether the CLI asked for bracketed paste (DECSET 2004); pyte stores private modes shifted by 5 bits."""
        with self.lock:
            return (2004 << 5) in self.screen.mode

    def resize(self, cols: int, rows: int) -> None:
        if (cols, rows) != (self.screen.columns, self.screen.lines):
            self._apply_size(cols, rows)
            if not self.exited:
                self._winsize(cols, rows)

    def send(self, data: bytes) -> None:
        fd = self._fd
        if data and fd is not None and not self.exited:
            self._writes.put(data)  # written off the caller's thread: a busy CLI must not freeze the UI

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
        if not self.measured:
            how = "cgroup cap, memory not measured" if self._capped else "memory not measured or capped"
            return f"{self.label} · {self.memory_limit_mb} MB limit [{how}] · ctrl+] leaves"
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
            with self.lock:
                try:
                    self._stream.feed(self._sanitizer.feed(data))
                except Exception as e:  # a sequence pyte cannot parse must never take the screen down
                    # never the bytes or the message: both can quote the user's conversation
                    logger.warning("cli_terminal_unparsed_output", length=len(data), error=type(e).__name__)
                replies = self._sanitizer.take_replies()
                self.version += 1
            for reply in replies:
                self.send(reply)
        self.exited = True
        self._closing.set()
        self._writes.put(None)
        if self._record is not None:
            try:
                self._record.close()
            except OSError:
                pass
            self._record = None
        with self.lock:
            self.version += 1
        if self.on_exit:
            self.on_exit()
        try:
            os.waitpid(pid, 0)
        except OSError:
            pass
        self._fd = None
        try:
            os.close(fd)
        except OSError:
            pass

    def _write(self) -> None:
        while True:
            data = self._writes.get()
            fd = self._fd
            if data is None or fd is None or self.exited:
                return
            try:
                view = memoryview(data)
                while view:
                    view = view[os.write(fd, view):]
            except OSError:
                pass

    def _watch(self) -> None:
        while not self._closing.wait(2.0):
            if self._scoped and not self._capped:
                self._capped = ensure_cap(self._pid, self.memory_limit_mb)
            rss = tree_rss_mb(self._pid)
            self.measured = rss is not None
            if rss is None:
                continue
            self.rss = rss
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
        fd = self._fd
        if fd is None or self.exited:
            return
        try:
            fcntl.ioctl(fd, termios.TIOCSWINSZ, struct.pack("HHHH", rows, cols, 0, 0))
        except OSError:
            return
        self._kill(signal.SIGWINCH)

    def _kill(self, sig: int) -> None:
        # Once the CLI has ended the pid is reaped and may belong to another process.
        if self._pid is None or self.exited:
            return
        try:
            os.killpg(os.getpgid(self._pid), sig)
        except OSError:
            pass
