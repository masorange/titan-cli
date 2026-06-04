"""In-memory browser session management for the local web adapter."""

from __future__ import annotations

from dataclasses import dataclass, field
import uuid
from typing import Any


@dataclass(slots=True)
class BrowserSession:
    """Minimal local browser session state."""

    session_id: str
    active_run_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class BrowserSessionManager:
    """Manage ephemeral browser sessions for the local UI backend."""

    def __init__(self) -> None:
        self._sessions: dict[str, BrowserSession] = {}

    def open_session(self) -> BrowserSession:
        """Create and store a new browser session."""
        session = BrowserSession(session_id=f"session-{uuid.uuid4()}")
        self._sessions[session.session_id] = session
        return session

    def get_session(self, session_id: str) -> BrowserSession | None:
        """Return a previously opened session if it exists."""
        return self._sessions.get(session_id)

    def set_active_run(self, session_id: str, run_id: str | None) -> BrowserSession | None:
        """Update the active run associated with a browser session."""
        session = self._sessions.get(session_id)
        if session is None:
            return None
        session.active_run_id = run_id
        return session
