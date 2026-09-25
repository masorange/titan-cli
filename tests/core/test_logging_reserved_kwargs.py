"""No log call may pass `event=` as a keyword: structlog reserves it for the message.

`logger.info("review_published", event=event)` raises "got multiple values for argument
'event'" at runtime -- on 2026-09-24 it failed the Review PR submit step AFTER the review had
been published, so the user saw a failure for a review that went out. Nothing exercises every
log line, so this is checked in the source instead.
"""

import ast
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_LOG_METHODS = {"debug", "info", "warning", "warn", "error", "exception", "critical", "msg"}


def _offending_calls(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        if node.func.attr not in _LOG_METHODS:
            continue
        receiver = node.func.value
        name = receiver.id if isinstance(receiver, ast.Name) else getattr(receiver, "attr", "")
        if "log" not in name.lower():
            continue
        if any(keyword.arg == "event" for keyword in node.keywords):
            found.append(f"{path.relative_to(_ROOT)}:{node.lineno}")
    return found


def test_no_log_call_passes_event_as_a_keyword():
    sources = [
        path
        for base in (_ROOT / "titan_cli", _ROOT / "plugins")
        for path in base.rglob("*.py")
        if "/tests/" not in str(path) and ".venv" not in path.parts
    ]
    offending = [hit for path in sources for hit in _offending_calls(path)]
    assert not offending, "rename the `event=` keyword (reserved by structlog): " + ", ".join(offending)
