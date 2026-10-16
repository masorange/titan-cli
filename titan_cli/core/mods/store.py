"""A mod's store: small JSON values that outlive the session (a choice the person made)."""

import json
import os
import tempfile
import threading
from pathlib import Path
from typing import Any, Callable

from titan_cli.core.logging import get_logger

logger = get_logger(__name__)

# App state, not configuration: beside the logs (XDG state), out of ~/.titan,
# which holds what the user edits.
STORE_DIR = Path.home() / ".local" / "state" / "titan" / "mods"


class ModStore:
    def __init__(self, mod: str, root: Callable[[], Path] = lambda: STORE_DIR):
        self._mod = mod
        self._root = root
        self._lock = threading.Lock()

    @property
    def path(self) -> Path:
        return self._root() / f"{self._mod}.json"

    def _read(self) -> dict:
        try:
            data = json.loads(self.path.read_text())
        except (OSError, ValueError):
            return {}
        return data if isinstance(data, dict) else {}

    def get(self, key: str, default: Any = None) -> Any:
        with self._lock:
            return self._read().get(key, default)

    def set(self, key: str, value: Any) -> None:
        """Store a JSON-serialisable value; a failed write is logged, never raised."""
        with self._lock:
            data = self._read()
            data[key] = value
            try:
                self._write(data)
            except (OSError, TypeError, ValueError):
                logger.warning("mod_store_write_failed", mod=self._mod, key=key, exc_info=True)

    def _write(self, data: dict) -> None:
        """Write beside the target and rename over it, so a crash never leaves half a file."""
        text = json.dumps(data, indent=2)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=self.path.parent, prefix=f".{self._mod}.", suffix=".tmp")
        try:
            with os.fdopen(fd, "w") as f:
                f.write(text)
            os.replace(tmp, self.path)
        except BaseException:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise
