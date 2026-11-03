"""
The CLI sessions of this Titan run, shared by the `cli` mod (its menu) and the `cli` workspace (the terminal).

Neither imports the other: both read and drive this one registry and ask it to tell them when something
changes, so each repaints. Sessions live as long as Titan does; `stop_all` ends them when it quits.
"""
import atexit
import itertools
import os
from typing import Callable, Dict, List, Optional, Tuple

from titan_cli.external_cli.configs import CLI_REGISTRY
from titan_cli.external_cli.launcher import CLILauncher

from .session import Session, warm_scope_probe

DEFAULT_MEMORY_LIMIT_MB = 2048


def installed() -> List[Tuple[str, str]]:
    """The CLIs Titan knows (`CLI_REGISTRY`) that are installed, as (command, display name)."""
    return [(name, cfg["display_name"]) for name, cfg in CLI_REGISTRY.items() if CLILauncher(name).is_available()]


class SessionRegistry:
    def __init__(self) -> None:
        self.sessions: List[Session] = []  # every session started, running or exited, in order
        self.active_id: Optional[int] = None  # the one the workspace shows
        self.memory_limit_mb = DEFAULT_MEMORY_LIMIT_MB
        self._ids = itertools.count(1)
        self._listeners: Dict[str, Callable[[], None]] = {}

    def subscribe(self, key: str, listener: Callable[[], None]) -> None:
        """Call `listener` whenever the sessions or the active one change; a key again replaces its listener."""
        self._listeners[key] = listener

    def active(self) -> Optional[Session]:
        return next((s for s in self.sessions if s.id == self.active_id), None)

    def launch(self, command: str, label: str) -> Session:
        """A new session of `command`, made the active one. The widget that shows it starts the process."""
        warm_scope_probe()  # off the UI thread, so the first start finds the answer cached
        same = sum(1 for s in self.sessions if s.command == command)
        session = Session(next(self._ids), command, label if not same else f"{label} #{same + 1}",
                          os.getcwd(), self.memory_limit_mb)
        session.on_exit = self._changed
        self.sessions.append(session)
        self.active_id = session.id
        self._changed()
        return session

    def select(self, sid: int) -> None:
        self.active_id = sid
        self._changed()

    def close(self, sid: Optional[int] = None) -> None:
        """Stop a session (the active one by default) and drop it; the last one left becomes the active one."""
        target = next((s for s in self.sessions if s.id == (sid if sid is not None else self.active_id)), None)
        if target is None:
            return
        target.stop()
        self.sessions = [s for s in self.sessions if s is not target]
        self.active_id = self.sessions[-1].id if self.sessions else None
        self._changed()

    def stop_all(self) -> None:
        for session in self.sessions:
            session.stop(now=True)

    def _changed(self) -> None:
        for listener in list(self._listeners.values()):
            listener()


SESSIONS = SessionRegistry()
atexit.register(SESSIONS.stop_all)
