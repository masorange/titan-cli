"""Provider-neutral OAuth events."""

from __future__ import annotations

from dataclasses import dataclass, field
from queue import Empty, Full, Queue
from threading import Lock
from typing import Any, Protocol


@dataclass(frozen=True)
class OAuthEvent:
    """A safe OAuth lifecycle event.

    Events must never include raw access tokens or refresh tokens.
    """

    type: str
    operation_id: str
    credential_key: str | None = None
    provider: str | None = None
    connection_id: str | None = None
    message: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


class OAuthEventSink(Protocol):
    """Receives OAuth lifecycle events."""

    def emit(self, event: OAuthEvent) -> None:
        """Handle an OAuth event."""


class NullOAuthEventSink:
    """Event sink that intentionally discards every OAuth event."""

    def emit(self, event: OAuthEvent) -> None:
        """Discard an OAuth event."""


class CollectingOAuthEventSink:
    """Event sink useful for tests and headless callers."""

    def __init__(self) -> None:
        self.events: list[OAuthEvent] = []

    def emit(self, event: OAuthEvent) -> None:
        """Record an OAuth event."""
        self.events.append(event)


class QueuedOAuthEventSink:
    """Thread-safe queue-backed sink for runtime event dispatchers."""

    def __init__(self, maxsize: int = 0) -> None:
        self.queue: Queue[OAuthEvent] = Queue(maxsize=maxsize)
        self._dropped_count = 0
        self._dropped_count_lock = Lock()

    def emit(self, event: OAuthEvent) -> None:
        """Queue an OAuth event without allowing overflow to abort OAuth."""
        try:
            self.queue.put_nowait(event)
        except Full:
            self._record_dropped_event()

    @property
    def dropped_count(self) -> int:
        """Return how many events were dropped because the queue was full."""
        with self._dropped_count_lock:
            return self._dropped_count

    def get(
        self,
        *,
        block: bool = True,
        timeout: float | None = None,
    ) -> OAuthEvent | None:
        """Return the next queued event, or None when no event is available."""
        try:
            return self.queue.get(block=block, timeout=timeout)
        except Empty:
            return None

    def drain(self) -> list[OAuthEvent]:
        """Return all currently queued events."""
        events = []
        while True:
            event = self.get(block=False)
            if event is None:
                return events
            events.append(event)

    def _record_dropped_event(self) -> None:
        """Record a dropped event without blocking the OAuth flow."""
        with self._dropped_count_lock:
            self._dropped_count += 1
