"""
Shared pause for GitHub's API rate limit.

Every `gh` call of the process goes through `GHNetwork.run_command`. Once GitHub answers
"rate limit exceeded", more calls only fail the same way, so they are refused here until the
limit resets, with the time in the message.
"""
import subprocess
import threading
import time
from datetime import datetime
from typing import Optional

#: How long to wait when GitHub does not say when the limit resets.
FALLBACK_SECONDS = 300

_lock = threading.Lock()
_until: float = 0.0


def is_rate_limit(text: str) -> bool:
    return "rate limit" in text.lower()


def _reset_time() -> Optional[float]:
    """When GitHub says the exhausted limit resets. `api rate_limit` itself does not count."""
    try:
        out = subprocess.run(
            ["gh", "api", "rate_limit", "--jq", "[.resources[].reset] | max"],
            capture_output=True, text=True, timeout=10, check=True,
        ).stdout.strip()
        return float(out)
    except (subprocess.SubprocessError, ValueError, OSError):
        return None


def start_pause() -> None:
    """Refuse GitHub calls until the limit resets (or FALLBACK_SECONDS when unknown)."""
    global _until
    reset = _reset_time()
    now = time.time()
    until = reset if reset and reset > now else now + FALLBACK_SECONDS
    with _lock:
        _until = max(_until, until)


def paused_message() -> Optional[str]:
    """Why calls are refused, or None when they may go out."""
    with _lock:
        until = _until
    if until <= time.time():
        return None
    return f"GitHub API rate limit exceeded; paused until {datetime.fromtimestamp(until):%H:%M}"


def clear() -> None:
    global _until
    with _lock:
        _until = 0.0
