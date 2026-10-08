"""A mod's store: small JSON values that outlive the session (a choice the person made)."""

import json
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
            return json.loads(self.path.read_text())
        except (OSError, ValueError):
            return {}

    def get(self, key: str, default: Any = None) -> Any:
        with self._lock:
            return self._read().get(key, default)

    def set(self, key: str, value: Any) -> None:
        """Store a JSON-serialisable value; a failed write is logged, never raised."""
        with self._lock:
            data = self._read()
            data[key] = value
            try:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                self.path.write_text(json.dumps(data, indent=2))
            except (OSError, TypeError):
                logger.warning("mod_store_write_failed", mod=self._mod, key=key, exc_info=True)
