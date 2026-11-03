"""CLI sessions: coding CLIs (Claude, Codex, Gemini...) run in a PTY and shown as a terminal screen."""
from .emulation import (
    Sanitizer, TermScreen, TermStream, key_bytes, paste_bytes, render_line,
)
from .registry import DEFAULT_MEMORY_LIMIT_MB, SESSIONS, SessionRegistry, installed
from .session import Session

__all__ = [
    "DEFAULT_MEMORY_LIMIT_MB", "SESSIONS", "Sanitizer", "Session", "SessionRegistry", "TermScreen",
    "TermStream", "installed", "key_bytes", "paste_bytes", "render_line",
]
