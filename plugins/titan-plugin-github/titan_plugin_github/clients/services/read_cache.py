"""
A short memory for the reads that timers repeat.

The github mod and the github workspace poll the same lists on the same client. Within
`TTL_SECONDS` a second ask is answered from the first one's result, so two views (and the
three PR lists, which all read the same repository listing) cost one GitHub call, not several.
Only successes are kept. `invalidate()` forgets everything, for the reads that follow a change
or that the user asked to repeat.
"""
import functools
import threading
import time
from typing import Any, Callable, Dict, Hashable, Optional, Tuple

from titan_cli.core.result import ClientSuccess

TTL_SECONDS = 15


class ReadCache:
    def __init__(self, ttl: float = TTL_SECONDS):
        self._ttl = ttl
        self._lock = threading.Lock()
        self._items: Dict[Hashable, Tuple[float, Any]] = {}

    def get(self, key: Hashable) -> Optional[Any]:
        with self._lock:
            hit = self._items.get(key)
        if hit is None or time.monotonic() - hit[0] > self._ttl:
            return None
        return hit[1]

    def put(self, key: Hashable, value: Any) -> None:
        with self._lock:
            self._items[key] = (time.monotonic(), value)

    def invalidate(self) -> None:
        with self._lock:
            self._items.clear()


def cached_read(fn: Callable) -> Callable:
    """Answer a repeated call of a service method from its last success (needs `self._reads`)."""
    @functools.wraps(fn)
    def wrapper(self, *args, **kwargs):
        key = (fn.__name__, args, tuple(sorted(kwargs.items())))
        hit = self._reads.get(key)
        if hit is not None:
            return hit
        result = fn(self, *args, **kwargs)
        if isinstance(result, ClientSuccess):
            self._reads.put(key, result)
        return result
    return wrapper
