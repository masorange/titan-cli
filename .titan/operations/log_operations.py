"""
Log Parsing and Analysis Operations

Pure business logic for parsing and analyzing titan structured log files.
Log format: JSON lines (structlog), with plain-text SESSION START separators.
"""

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

SLOW_THRESHOLD_SECONDS = 2.0
SESSION_MARKER = "SESSION START"

STEP_RESULT_ICONS = {
    "success": "✅",
    "failed": "❌",
    "skipped": "⏭️",
    "exit": "⏹️",
    "exception": "💥",
    "incomplete": "⚠️",
}

WORKFLOW_STATUS_ICONS = {
    "success": "✅",
    "failed": "❌",
    "exited": "⏹️",
    "incomplete": "⚠️",
    "unknown": "❓",
}


@dataclass
class LogEntry:
    timestamp: Optional[datetime]
    level: str
    event: str
    raw: Dict[str, Any]


@dataclass
class StepRun:
    step_id: str
    result: str        # success / failed / skipped / exit / exception
    duration: Optional[float]
    message: Optional[str]
    error: Optional[str]
    workflow: str


@dataclass
class WorkflowRun:
    name: str
    status: str        # success / failed / exited / incomplete / unknown
    duration: Optional[float]
    steps: List[StepRun] = field(default_factory=list)
    failed_at: Optional[str] = None


@dataclass
class LogSession:
    start_time: Optional[datetime]
    pid: Optional[int]
    version: Optional[str] = None
    mode: Optional[str] = None
    entries: List[LogEntry] = field(default_factory=list)

    @property
    def end_time(self) -> Optional[datetime]:
        for e in reversed(self.entries):
            if e.timestamp:
                return e.timestamp
        return None

    @property
    def duration_seconds(self) -> Optional[float]:
        if self.start_time and self.end_time:
            start = self.start_time
            end = self.end_time
            # Strip timezone info for comparison if needed
            if start.tzinfo and not end.tzinfo:
                end = end.replace(tzinfo=timezone.utc)
            elif end.tzinfo and not start.tzinfo:
                start = start.replace(tzinfo=timezone.utc)
            return (end - start).total_seconds()
        return None


@dataclass
class SessionAnalysis:
    session: LogSession
    workflows: List[WorkflowRun]
    errors: List[LogEntry]
    warnings: List[LogEntry]
    slow_ops: List[LogEntry]


def parse_log_file(path: Path) -> List[LogSession]:
    """
    Parse a titan log file and split it into sessions.

    Args:
        path: Path to the log file

    Returns:
        List of LogSession objects, oldest first
    """
    sessions: List[LogSession] = []
    current_entries: List[LogEntry] = []
    current_start_time: Optional[datetime] = None
    current_pid: Optional[int] = None
    current_version: Optional[str] = None
    current_mode: Optional[str] = None

    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue

            if SESSION_MARKER in line:
                # Save previous session
                if current_entries or current_start_time:
                    sessions.append(LogSession(
                        start_time=current_start_time,
                        pid=current_pid,
                        version=current_version,
                        mode=current_mode,
                        entries=current_entries,
                    ))
                current_entries = []
                current_start_time = _parse_session_time(line)
                current_pid = _parse_session_pid(line)
                current_version = None
                current_mode = None
                continue

            # Skip plain-text separator lines (─────)
            if line.startswith("─") or line.startswith("-" * 10):
                continue

            entry = _parse_log_entry(line)
            if entry:
                if entry.event == "session_started" and current_version is None:
                    current_version = entry.raw.get("version")
                    current_mode = entry.raw.get("mode")
                current_entries.append(entry)

    # Don't forget the last session
    if current_entries or current_start_time:
        sessions.append(LogSession(
            start_time=current_start_time,
            pid=current_pid,
            version=current_version,
            mode=current_mode,
            entries=current_entries,
        ))

    return sessions


def analyze_session(session: LogSession) -> SessionAnalysis:
    """
    Analyze a log session and extract workflows, errors, warnings and slow ops.

    Args:
        session: LogSession to analyze

    Returns:
        SessionAnalysis with all extracted information
    """
    workflows = _extract_workflows(session.entries)
    errors = [e for e in session.entries if e.level in ("error", "exception")]
    warnings = [e for e in session.entries if e.level == "warning"]
    slow_ops = [
        e for e in session.entries
        if e.raw.get("duration", 0) >= SLOW_THRESHOLD_SECONDS
    ]

    return SessionAnalysis(
        session=session,
        workflows=workflows,
        errors=errors,
        warnings=warnings,
        slow_ops=slow_ops,
    )


def format_session_label(session: LogSession) -> str:
    """
    Format a session label for display in a selection list.

    Args:
        session: LogSession to format

    Returns:
        Human-readable label string
    """
    time_str = (
        session.start_time.strftime("%Y-%m-%d  %H:%M:%S")
        if session.start_time
        else "Unknown time"
    )
    pid_str = f"  PID {session.pid}" if session.pid else ""
    dur = session.duration_seconds
    dur_str = f"  {dur:.0f}s" if dur else ""

    error_count = sum(1 for e in session.entries if e.level in ("error", "exception"))
    error_str = f"  ⚠ {error_count} error{'s' if error_count != 1 else ''}" if error_count else ""

    entry_count = len(session.entries)

    return f"{time_str}{pid_str}{dur_str}  —  {entry_count} events{error_str}"


# ── Private helpers ────────────────────────────────────────────────────────────

def _parse_log_entry(line: str) -> Optional[LogEntry]:
    try:
        data = json.loads(line)
    except (json.JSONDecodeError, ValueError):
        return None

    timestamp = None
    ts_str = data.get("timestamp")
    if ts_str:
        try:
            timestamp = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        except ValueError:
            pass

    return LogEntry(
        timestamp=timestamp,
        level=data.get("level", "unknown"),
        event=data.get("event", ""),
        raw=data,
    )


def _parse_session_time(line: str) -> Optional[datetime]:
    match = re.search(r"SESSION START\s+(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})", line)
    if match:
        try:
            return datetime.strptime(match.group(1), "%Y-%m-%d %H:%M:%S")
        except ValueError:
            pass
    return None


def _parse_session_pid(line: str) -> Optional[int]:
    match = re.search(r"PID\s+(\d+)", line)
    if match:
        try:
            return int(match.group(1))
        except ValueError:
            pass
    return None


def _extract_workflows(entries: List[LogEntry]) -> List[WorkflowRun]:
    workflows: List[WorkflowRun] = []
    # Track active workflows by name (most workflows run sequentially)
    active: Dict[str, WorkflowRun] = {}

    for entry in entries:
        event = entry.event
        raw = entry.raw
        wf_name = raw.get("workflow", "")

        if event == "workflow_started":
            active[wf_name] = WorkflowRun(name=wf_name, status="incomplete", duration=None)

        elif event == "workflow_completed":
            run = active.pop(wf_name, WorkflowRun(name=wf_name, status="unknown", duration=None))
            run.status = raw.get("status", "success")
            run.duration = raw.get("duration")
            workflows.append(run)

        elif event == "workflow_failed":
            run = active.pop(wf_name, WorkflowRun(name=wf_name, status="unknown", duration=None))
            run.status = "failed"
            run.duration = raw.get("duration")
            run.failed_at = raw.get("failed_at_step")
            workflows.append(run)

        elif event in ("step_success", "step_failed", "step_skipped", "step_exit", "step_exception"):
            result_map = {
                "step_success": "success",
                "step_failed": "failed",
                "step_skipped": "skipped",
                "step_exit": "exit",
                "step_exception": "exception",
            }
            run = active.get(wf_name)
            if run:
                run.steps.append(StepRun(
                    step_id=raw.get("step_id", ""),
                    result=result_map[event],
                    duration=raw.get("duration"),
                    message=raw.get("message") or raw.get("reason"),
                    error=raw.get("error"),
                    workflow=wf_name,
                ))

    # Workflows that never completed (app closed mid-run)
    for run in active.values():
        workflows.append(run)

    return workflows


__all__ = [
    "LogEntry",
    "LogSession",
    "WorkflowRun",
    "StepRun",
    "SessionAnalysis",
    "SLOW_THRESHOLD_SECONDS",
    "STEP_RESULT_ICONS",
    "WORKFLOW_STATUS_ICONS",
    "parse_log_file",
    "analyze_session",
    "format_session_label",
]
