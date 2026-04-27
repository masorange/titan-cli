"""Simple in-memory event bus for workflow runs."""

from __future__ import annotations

from collections import defaultdict
from typing import Callable

from titan_cli.application.models.events import RunEvent


class EventBus:
    """Publish/subscribe event bus for structured workflow events."""

    def __init__(self) -> None:
        self._subscribers: dict[str, list[Callable[[RunEvent], None]]] = defaultdict(list)

    def publish(self, event: RunEvent) -> None:
        """Publish an event to all subscribers for its run."""
        for callback in list(self._subscribers[event.run_id]):
            callback(event)

    def subscribe(self, run_id: str, callback: Callable[[RunEvent], None]) -> None:
        """Subscribe to events for the given run."""
        self._subscribers[run_id].append(callback)

    def unsubscribe(self, run_id: str, callback: Callable[[RunEvent], None]) -> None:
        """Remove a subscriber for the given run when present."""
        callbacks = self._subscribers.get(run_id)
        if not callbacks:
            return
        try:
            callbacks.remove(callback)
        except ValueError:
            return
        if not callbacks:
            del self._subscribers[run_id]
