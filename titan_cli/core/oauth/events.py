"""Provider-neutral OAuth events."""

from __future__ import annotations

from dataclasses import dataclass, field
from queue import Empty, Queue
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

    def emit(self, event: OAuthEvent) -> None:
        """Queue an OAuth event without exposing token material."""
        self.queue.put_nowait(event)

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
