"""A mod's state: values that outlive screens, and redraw the mod's panes when they change."""

import threading
from typing import Any, Callable, Dict


class ModState:
    def __init__(self, on_change: Callable[[], None]):
        self._values: Dict[str, Any] = {}
        self._lock = threading.Lock()
        self._on_change = on_change

    def get(self, key: str, default: Any = None) -> Any:
        with self._lock:
            return self._values.get(key, default)

    def set(self, key: str, value: Any) -> None:
        with self._lock:
            self._values[key] = value
        self._on_change()

    def update(self, key: str, fn: Callable[[Any], Any], default: Any = None) -> Any:
        """Replace the value with `fn(current)` atomically and return the new one."""
        with self._lock:
            value = fn(self._values.get(key, default))
            self._values[key] = value
        self._on_change()
        return value
