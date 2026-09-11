"""
Log Parsing and Analysis Operations

Pure business logic for reading titan structured log files.

Log format: JSON lines (structlog), separated by plain-text `SESSION START`
banner lines. The logger rotates at a fixed size, so a single run can be
split across `titan.log` and `titan.log.N`: the tail of a session lives in
the newer file with no banner of its own. Everything here works on the whole
rotation set, in chronological order, so a rotated session is still one
session.

Reading is two-phase on purpose. `index_sessions` walks the bytes and records
where each session lives without building objects for lines nobody will look
at; `load_session` then parses only the segments of the one session the user
picked. A full parse of every rotation is ~40 MB of JSON for a question that
usually concerns thirty seconds of one run.
"""

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

SLOW_THRESHOLD_SECONDS = 2.0
SESSION_MARKER = "SESSION START"
_SESSION_MARKER_BYTES = b"SESSION START"

DEFAULT_LOG_DIR = Path.home() / ".local" / "state" / "titan" / "logs"
DEFAULT_LOG_NAME = "titan.log"
# Reports land outside the repository on purpose: they are scratch output of
# a diagnosis, not project files, and should never show up in `git status`.
DEFAULT_REPORT_DIR = Path.home() / ".local" / "state" / "titan" / "diagnostics"

# structlog emits lowercase level names. "exception" is not one of them —
# an exception is logged at "error" with the traceback in the payload.
ERROR_LEVELS = {"error", "critical", "fatal"}

# Events the workflow timeline already renders. They are excluded from the
# error list and the slow-operations list so those sections say something the
# timeline above them does not.
ENGINE_TIMELINE_EVENTS = {
    "workflow_started",
    "workflow_completed",
    "workflow_failed",
    "workflow_aborted_on_app_exit",
    "step_started",
    "step_success",
    "step_failed",
    "step_skipped",
    "step_exit",
    "step_exception",
}

_STEP_EVENT_RESULTS = {
    "step_success": "success",
    "step_failed": "failed",
    "step_skipped": "skipped",
    "step_exit": "exit",
    "step_exception": "exception",
}

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
    "aborted": "🛑",
    "incomplete": "⚠️",
    "unknown": "❓",
}

STEP_RESULT_LEGEND = "✅ ok   ❌ failed   💥 exception   ⏹️ exit   ⏭️ skipped"

LEVEL_ICONS = {
    "debug": "·",
    "info": "i",
    "warning": "!",
    "error": "✖",
    "critical": "✖",
    "fatal": "✖",
}


# ── Data model ─────────────────────────────────────────────────────────────────

@dataclass
class LogFileInfo:
    """A log file on disk, current or rotated."""
    path: Path
    size_bytes: int
    modified: datetime
    rotation_index: int  # 0 = current titan.log, 1 = titan.log.1, ...

    @property
    def is_current(self) -> bool:
        return self.rotation_index == 0

    @property
    def size_mb(self) -> float:
        return self.size_bytes / (1024 * 1024)


@dataclass
class LogEntry:
    timestamp: Optional[datetime]
    level: str
    event: str
    raw: Dict[str, Any]
    source: Optional[Path] = None
    # Lazily built lowercase rendering of `raw`, so a text filter over 20k
    # entries serializes each payload once instead of once per keystroke.
    # Kept off `raw` so it never shows up in a payload dump.
    search_blob: Optional[str] = field(default=None, repr=False, compare=False)


@dataclass
class SessionSegment:
    """A contiguous byte range of one file belonging to one session."""
    path: Path
    start_offset: int
    end_offset: int


@dataclass
class SessionRef:
    """
    Where a session lives and what it contains, without its entries.

    Produced by `index_sessions` from a byte scan; enough to render the
    selector, and enough for `load_session` to read the session back.
    """
    segments: List[SessionSegment] = field(default_factory=list)
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    pid: Optional[int] = None
    version: Optional[str] = None
    mode: Optional[str] = None
    entry_count: int = 0
    error_count: int = 0
    warning_count: int = 0
    # A session with no banner of its own: its head was in a file that has
    # already been deleted by rotation, so what remains is a tail.
    truncated_head: bool = False

    @property
    def spans_rotation(self) -> bool:
        return len({segment.path for segment in self.segments}) > 1

    @property
    def files(self) -> List[Path]:
        seen: List[Path] = []
        for segment in self.segments:
            if segment.path not in seen:
                seen.append(segment.path)
        return seen

    @property
    def duration_seconds(self) -> Optional[float]:
        if self.start_time and self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return None


@dataclass
class StepRun:
    step_id: str
    result: str        # success / failed / skipped / exit / exception
    duration: Optional[float]
    message: Optional[str]
    error: Optional[str]
    workflow: str
    timestamp: Optional[datetime] = None
    started_at: Optional[datetime] = None
    plugin: Optional[str] = None
    # Everything logged while this step was running, in order. This is where
    # the cause of a failure actually lives: the step's own error line says
    # what broke, the entries behind it say why.
    entries: List["LogEntry"] = field(default_factory=list)

    @property
    def failed(self) -> bool:
        return self.result in ("failed", "exception")

    @property
    def suspect(self) -> bool:
        """
        Worth investigating: it failed, or it never finished. A step that was
        still running when the log ends is the prime suspect for a hang or a
        crash, and has no error line of its own to give it away.
        """
        return self.failed or self.result == "incomplete"


@dataclass
class WorkflowRun:
    name: str
    status: str        # success / failed / exited / aborted / incomplete / unknown
    duration: Optional[float]
    steps: List[StepRun] = field(default_factory=list)
    failed_at: Optional[str] = None
    started_at: Optional[datetime] = None

    @property
    def status_label(self) -> str:
        """
        Say in words how the run ended.

        An icon alone cannot distinguish "the workflow failed" from "the log
        simply stops here", and those call for opposite reactions.
        """
        if self.status == "success":
            return "completed"
        if self.status == "failed":
            return f"failed at '{self.failed_at}'" if self.failed_at else "failed"
        if self.status == "exited":
            return "exited early"
        if self.status == "aborted":
            return "aborted when the app closed"
        if self.status == "incomplete":
            return "no completion logged — still running when the log ends"
        return "outcome not in the log"

    @property
    def step_summary(self) -> str:
        """Counts per step result, e.g. `9 ok · 1 skipped`."""
        labels = {
            "success": "ok",
            "failed": "failed",
            "skipped": "skipped",
            "exit": "exit",
            "exception": "exception",
        }
        counts: Dict[str, int] = {}
        for step in self.steps:
            counts[step.result] = counts.get(step.result, 0) + 1
        if not counts:
            return "no steps recorded"
        ordered = [
            f"{counts[result]} {labels.get(result, result)}"
            for result in ("success", "failed", "exception", "exit", "skipped")
            if result in counts
        ]
        return f"{len(self.steps)} steps · " + " · ".join(ordered)


@dataclass
class LogSession:
    """A fully parsed session."""
    ref: SessionRef
    entries: List[LogEntry] = field(default_factory=list)

    @property
    def start_time(self) -> Optional[datetime]:
        return self.ref.start_time

    @property
    def pid(self) -> Optional[int]:
        return self.ref.pid

    @property
    def version(self) -> Optional[str]:
        return self.ref.version

    @property
    def mode(self) -> Optional[str]:
        return self.ref.mode

    @property
    def end_time(self) -> Optional[datetime]:
        for entry in reversed(self.entries):
            if entry.timestamp:
                return entry.timestamp
        return self.ref.end_time

    @property
    def duration_seconds(self) -> Optional[float]:
        start, end = self.start_time, self.end_time
        if start and end:
            return (end - start).total_seconds()
        return None


@dataclass
class EntryGroup:
    """Repeated identical entries collapsed into one row."""
    entry: LogEntry          # first occurrence
    count: int
    last_timestamp: Optional[datetime]

    @property
    def message(self) -> str:
        return entry_message(self.entry)


@dataclass
class SessionAnalysis:
    session: LogSession
    workflows: List[WorkflowRun]
    errors: List[EntryGroup]          # error-level entries NOT in the timeline
    warnings: List[EntryGroup]      # only those logged inside a step
    slow_ops: List[LogEntry]
    warnings_outside_steps: int = 0
    error_entry_count: int = 0        # every error-level entry
    timeline_error_count: int = 0     # of those, the ones the timeline shows
    # Errors partitioned by the step they happened in. An error inside a step
    # that went on to succeed did not break this session — the test suite
    # logs hundreds of them — while an error inside the step that failed is
    # the thing being looked for.
    implicated_errors: List[EntryGroup] = field(default_factory=list)
    incidental_errors: List[EntryGroup] = field(default_factory=list)
    unattributed_errors: List[EntryGroup] = field(default_factory=list)
    incidental_error_count: int = 0
    failed_steps: List[StepRun] = field(default_factory=list)
    provider_events: List[LogEntry] = field(default_factory=list)

    @property
    def quota_exhausted_providers(self) -> List[str]:
        """CLIs that reported a spent quota, newest occurrence last."""
        names: List[str] = []
        for entry in self.provider_events:
            if entry.raw.get("quota_exhausted") is not True:
                continue
            name = entry.raw.get("cli") or entry.raw.get("provider")
            if name and str(name) not in names:
                names.append(str(name))
        return names

    @property
    def looks_like_test_noise(self) -> bool:
        """
        Whether the errors outside any step look like a test suite writing
        into the same log file.

        The signature is a dense burst of many DIFFERENT `*_failed` events
        with no workflow running — real breakage does not fail forty distinct
        operations in ten seconds while idle. Reported as an observation, not
        a certainty: nothing in the log states who wrote a line.
        """
        groups = self.unattributed_errors
        if len(groups) < 20:
            return False
        stamps = [g.entry.timestamp for g in groups if g.entry.timestamp]
        if len(stamps) < 2:
            return False
        span = (max(stamps) - min(stamps)).total_seconds()
        return span <= 60


# ── File discovery ─────────────────────────────────────────────────────────────

def discover_log_files(directory: Path = DEFAULT_LOG_DIR) -> List[LogFileInfo]:
    """
    Find `titan.log` and its rotations in a directory.

    Args:
        directory: Directory to scan

    Returns:
        List of LogFileInfo, newest first (current log, then .1, .2, ...)
    """
    if not directory.is_dir():
        return []

    found: List[LogFileInfo] = []
    for path in directory.iterdir():
        if not path.is_file():
            continue
        rotation = _rotation_index(path.name)
        if rotation is None:
            continue
        stat = path.stat()
        found.append(LogFileInfo(
            path=path,
            size_bytes=stat.st_size,
            modified=datetime.fromtimestamp(stat.st_mtime).astimezone(),
            rotation_index=rotation,
        ))

    return sorted(found, key=lambda info: info.rotation_index)


def chronological_paths(files: Sequence[LogFileInfo]) -> List[Path]:
    """
    Order log files oldest-first, which is the order `index_sessions` needs
    to stitch a session back together across a rotation boundary.
    """
    return [info.path for info in sorted(files, key=lambda i: -i.rotation_index)]


def _rotation_index(name: str) -> Optional[int]:
    if name == DEFAULT_LOG_NAME:
        return 0
    match = re.fullmatch(re.escape(DEFAULT_LOG_NAME) + r"\.(\d+)", name)
    return int(match.group(1)) if match else None


# ── Phase 1: index ─────────────────────────────────────────────────────────────

def index_sessions(paths: Sequence[Path]) -> List[SessionRef]:
    """
    Scan log files and record where each session lives.

    Only lines that look like a level marker or a session banner are decoded;
    the rest are counted and skipped. Files must be given oldest-first so a
    session interrupted by rotation continues into the next file instead of
    starting a new one.

    Args:
        paths: Log file paths, oldest first

    Returns:
        List of SessionRef, oldest first
    """
    sessions: List[SessionRef] = []
    current: Optional[SessionRef] = None

    for path in paths:
        segment: Optional[SessionSegment] = None
        try:
            handle = open(path, "rb")
        except OSError:
            continue

        with handle as file:
            offset = 0
            for raw in file:
                line_start = offset
                offset += len(raw)
                stripped = raw.strip()
                if not stripped:
                    continue

                if _SESSION_MARKER_BYTES in stripped:
                    banner = _session_ref_from_banner(
                        stripped.decode("utf-8", errors="replace")
                    )
                    # Titan writes the banner twice at startup. Taking both at
                    # face value produced a phantom ten-entry session in front
                    # of every real one, doubling the selector.
                    if (
                        current is not None
                        and banner.pid is not None
                        and banner.pid == current.pid
                        and banner.start_time == current.start_time
                    ):
                        segment = SessionSegment(path, offset, offset)
                        current.segments.append(segment)
                        continue
                    current = banner
                    segment = SessionSegment(path, offset, offset)
                    current.segments.append(segment)
                    sessions.append(current)
                    continue

                if _is_separator(stripped):
                    continue

                if current is None:
                    # Entries before any banner: the head of this session was
                    # in a file rotation has already removed.
                    current = SessionRef(truncated_head=True)
                    sessions.append(current)
                    segment = None

                if segment is None:
                    segment = SessionSegment(path, line_start, line_start)
                    current.segments.append(segment)

                segment.end_offset = offset
                _accumulate(current, stripped)

    return sessions


def _session_ref_from_banner(line: str) -> SessionRef:
    return SessionRef(
        start_time=_parse_banner_time(line),
        pid=_parse_banner_pid(line),
    )


def _accumulate(ref: SessionRef, raw: bytes) -> None:
    ref.entry_count += 1

    timestamp = _extract_timestamp(raw)
    if timestamp:
        ref.end_time = timestamp
        if ref.start_time is None:
            ref.start_time = timestamp

    # Cheap gate before paying for json.loads: only a few percent of lines are
    # an error, a warning, or the session banner entry.
    if b'"level"' in raw and (b'"error"' in raw or b'"warning"' in raw
                              or b'"critical"' in raw or b'"fatal"' in raw):
        data = _loads(raw)
        if data:
            level = data.get("level")
            if level in ERROR_LEVELS:
                ref.error_count += 1
            elif level == "warning":
                ref.warning_count += 1

    if ref.version is None and b'"session_started"' in raw:
        data = _loads(raw)
        if data and data.get("event") == "session_started":
            ref.version = data.get("version")
            ref.mode = data.get("mode")
            if ref.pid is None:
                ref.pid = data.get("pid")


# ── Phase 2: load one session ──────────────────────────────────────────────────

def load_session(ref: SessionRef) -> LogSession:
    """
    Parse the entries of a single indexed session.

    Args:
        ref: SessionRef produced by `index_sessions`

    Returns:
        LogSession with all its entries parsed
    """
    entries: List[LogEntry] = []

    for segment in ref.segments:
        try:
            handle = open(segment.path, "rb")
        except OSError:
            continue

        with handle as file:
            file.seek(segment.start_offset)
            remaining = segment.end_offset - segment.start_offset
            while remaining > 0:
                raw = file.readline()
                if not raw:
                    break
                remaining -= len(raw)
                stripped = raw.strip()
                if not stripped or _is_separator(stripped):
                    continue
                entry = _parse_log_entry(stripped, segment.path)
                if entry:
                    entries.append(entry)

    return LogSession(ref=ref, entries=entries)


# ── Analysis ───────────────────────────────────────────────────────────────────

def analyze_session(session: LogSession) -> SessionAnalysis:
    """
    Extract workflows, errors, warnings and slow operations from a session.

    Args:
        session: LogSession to analyze

    Returns:
        SessionAnalysis with all extracted information
    """
    workflows = _extract_workflows(session.entries)

    error_entries = [e for e in session.entries if e.level in ERROR_LEVELS]
    timeline_errors = [e for e in error_entries if e.event in ENGINE_TIMELINE_EVENTS]
    other_errors = [e for e in error_entries if e.event not in ENGINE_TIMELINE_EVENTS]
    warnings = [e for e in session.entries if e.level == "warning"]

    slow_ops = [
        e for e in session.entries
        if e.event not in ENGINE_TIMELINE_EVENTS and _duration_of(e) is not None
        and _duration_of(e) >= SLOW_THRESHOLD_SECONDS
    ]
    slow_ops.sort(key=lambda e: _duration_of(e) or 0.0, reverse=True)

    failed_steps = [step for run in workflows for step in run.steps if step.suspect]

    # Which step was each error logged inside? Identity, not timestamps: the
    # windows were built by walking the same entry list.
    implicated_ids = {id(e) for step in failed_steps for e in step.entries}
    attributed_ids = {
        id(e)
        for run in workflows
        for step in run.steps
        for e in step.entries
    }

    implicated, incidental, unattributed = [], [], []
    for entry in other_errors:
        if id(entry) in implicated_ids:
            implicated.append(entry)
        elif id(entry) in attributed_ids:
            incidental.append(entry)
        else:
            unattributed.append(entry)

    # Warnings get the same treatment: the test-suite burst produces warnings
    # about PR #999 and TEST-123 that have nothing to do with this session.
    warnings_in_steps = [w for w in warnings if id(w) in attributed_ids]
    warnings_outside = len(warnings) - len(warnings_in_steps)

    return SessionAnalysis(
        session=session,
        workflows=workflows,
        errors=group_entries(other_errors),
        warnings=group_entries(warnings_in_steps),
        warnings_outside_steps=warnings_outside,
        slow_ops=slow_ops,
        error_entry_count=len(error_entries),
        timeline_error_count=len(timeline_errors),
        implicated_errors=group_entries(implicated),
        incidental_errors=group_entries(incidental),
        unattributed_errors=group_entries(unattributed),
        incidental_error_count=len(incidental),
        failed_steps=failed_steps,
        # Only entries logged inside a step: the same test-suite burst that
        # floods the error list also fakes provider calls, and those must not
        # be read as this session talking to a provider.
        provider_events=_provider_events(
            [e for e in session.entries if id(e) in attributed_ids]
        ),
    )


# Fields that mark an entry as a record of talking to an AI provider. The
# cause of an AI step failing is in these, and they are logged at debug or
# info level — so a report built only from error-level entries cannot see it.
_PROVIDER_FIELDS = ("quota_exhausted", "timed_out", "cli", "provider", "identifier")


def _provider_events(entries: Sequence[LogEntry]) -> List[LogEntry]:
    """
    Entries that record an AI provider call and say something went wrong with
    it — a spent quota, a timeout, a non-zero exit, or a routing decision.
    """
    found: List[LogEntry] = []
    seen: set = set()
    for entry in entries:
        raw = entry.raw
        if not any(field_name in raw for field_name in _PROVIDER_FIELDS):
            continue
        if entry.event in _PROMPT_DUMP_EVENTS:
            continue
        interesting = (
            raw.get("quota_exhausted") is True
            or raw.get("timed_out") is True
            or (isinstance(raw.get("exit_code"), int) and raw["exit_code"] != 0)
            or entry.event == "ai_route_resolved"
            or entry.level in ERROR_LEVELS
        )
        if not interesting:
            continue
        # The same routing decision is logged once per resolution; one line
        # each is enough to see which provider served which task.
        key = (entry.event, _compact_payload(entry))
        if key in seen:
            continue
        seen.add(key)
        found.append(entry)
    return found


def group_entries(entries: Sequence[LogEntry]) -> List[EntryGroup]:
    """
    Collapse repeated identical entries, preserving first-occurrence order.

    A retry loop or a per-item failure can log the same line hundreds of
    times; a table with one row per occurrence buries everything else.

    Args:
        entries: Entries to group

    Returns:
        List of EntryGroup in order of first occurrence
    """
    groups: Dict[Tuple[str, str], EntryGroup] = {}
    for entry in entries:
        key = (entry.event, entry_message(entry))
        group = groups.get(key)
        if group is None:
            groups[key] = EntryGroup(
                entry=entry, count=1, last_timestamp=entry.timestamp
            )
        else:
            group.count += 1
            if entry.timestamp:
                group.last_timestamp = entry.timestamp
    return list(groups.values())


def _extract_workflows(entries: Sequence[LogEntry]) -> List[WorkflowRun]:
    # Runs are appended when they START and updated in place when they end, so
    # the list stays in chronological order even when a run never completes.
    workflows: List[WorkflowRun] = []
    active: Dict[str, WorkflowRun] = {}
    # The step currently running, and the entries logged since it started.
    # Steps do not interleave, so one open slot is enough.
    open_step: Optional[Dict[str, Any]] = None

    for entry in entries:
        event = entry.event
        raw = entry.raw
        name = raw.get("workflow", "")

        if event == "step_started":
            open_step = {
                "step_id": raw.get("step_id", ""),
                "plugin": raw.get("plugin"),
                "started_at": entry.timestamp,
                "entries": [],
            }
            continue

        if open_step is not None and event not in ENGINE_TIMELINE_EVENTS:
            open_step["entries"].append(entry)

        if event == "workflow_started":
            run = WorkflowRun(
                name=name,
                status="incomplete",
                duration=None,
                started_at=entry.timestamp,
            )
            active[name] = run
            workflows.append(run)

        elif event == "workflow_completed":
            run = _close(active, workflows, name, entry)
            run.status = raw.get("status", "success")
            run.duration = raw.get("duration")

        elif event == "workflow_failed":
            run = _close(active, workflows, name, entry)
            run.status = "failed"
            run.duration = raw.get("duration")
            run.failed_at = raw.get("failed_at_step")

        elif event == "workflow_aborted_on_app_exit":
            run = _close(active, workflows, name, entry)
            run.status = "aborted"
            run.duration = raw.get("duration")

        elif event in _STEP_EVENT_RESULTS:
            run = active.get(name)
            if run is None:
                # A step logged for a workflow whose start we never saw (the
                # banner scrolled off in a rotation). Keep the step rather
                # than dropping it on the floor.
                run = WorkflowRun(
                    name=name,
                    status="incomplete",
                    duration=None,
                    started_at=entry.timestamp,
                )
                active[name] = run
                workflows.append(run)
            step_id = raw.get("step_id", "")
            # Claim the open window only if it belongs to this step; a step
            # whose start was never logged simply gets no entries.
            window = (
                open_step
                if open_step is not None and open_step["step_id"] == step_id
                else None
            )
            run.steps.append(StepRun(
                step_id=step_id,
                result=_STEP_EVENT_RESULTS[event],
                duration=raw.get("duration"),
                message=raw.get("message") or raw.get("reason"),
                error=raw.get("error"),
                workflow=name,
                timestamp=entry.timestamp,
                started_at=window["started_at"] if window else None,
                plugin=window["plugin"] if window else None,
                entries=window["entries"] if window else [],
            ))
            open_step = None

    # A step still running when the log ends never logs a result, so its
    # window would be discarded — exactly the entries that explain a hang or
    # a crash. Attach it to whatever run was open, marked as unfinished.
    if open_step is not None and open_step["entries"]:
        run = next(iter(active.values()), None)
        if run is None:
            run = WorkflowRun(
                name=open_step["entries"][0].raw.get("workflow", "(unknown workflow)"),
                status="incomplete",
                duration=None,
                started_at=open_step["started_at"],
            )
            workflows.append(run)
        run.steps.append(StepRun(
            step_id=open_step["step_id"],
            result="incomplete",
            duration=None,
            message="still running when the log ends",
            error=None,
            workflow=run.name,
            timestamp=open_step["entries"][-1].timestamp,
            started_at=open_step["started_at"],
            plugin=open_step["plugin"],
            entries=open_step["entries"],
        ))

    return workflows


def _close(
    active: Dict[str, WorkflowRun],
    workflows: List[WorkflowRun],
    name: str,
    entry: LogEntry,
) -> WorkflowRun:
    run = active.pop(name, None)
    if run is None:
        run = WorkflowRun(
            name=name, status="unknown", duration=None, started_at=entry.timestamp
        )
        workflows.append(run)
    return run


def _duration_of(entry: LogEntry) -> Optional[float]:
    value = entry.raw.get("duration")
    return float(value) if isinstance(value, (int, float)) else None


# ── Filtering and exploration ──────────────────────────────────────────────────

def filter_entries(
    entries: Sequence[LogEntry],
    *,
    levels: Optional[Iterable[str]] = None,
    workflow: Optional[str] = None,
    text: Optional[str] = None,
    since: Optional[datetime] = None,
    until: Optional[datetime] = None,
) -> List[LogEntry]:
    """
    Filter log entries by level, workflow, free text, and time range.

    Args:
        entries: Entries to filter
        levels: Keep only these levels (optional)
        workflow: Keep only entries of this workflow (optional)
        text: Case-insensitive substring matched against the whole raw entry (optional)
        since: Keep only entries at or after this instant (optional)
        until: Keep only entries at or before this instant (optional)

    Returns:
        Matching entries, in their original order
    """
    level_set = {level.lower() for level in levels} if levels else None
    needle = text.lower() if text else None

    result: List[LogEntry] = []
    for entry in entries:
        if level_set is not None and entry.level.lower() not in level_set:
            continue
        if workflow is not None and entry.raw.get("workflow") != workflow:
            continue
        if since is not None and (entry.timestamp is None or entry.timestamp < since):
            continue
        if until is not None and (entry.timestamp is None or entry.timestamp > until):
            continue
        if needle is not None and needle not in _searchable(entry):
            continue
        result.append(entry)
    return result


def entries_around(
    entries: Sequence[LogEntry],
    target: LogEntry,
    *,
    before: int = 15,
    after: int = 10,
) -> List[LogEntry]:
    """
    Return the entries surrounding one entry, for reading it in context.

    Args:
        entries: The full entry list of the session
        target: The entry to center on
        before: How many entries to include before it
        after: How many entries to include after it

    Returns:
        The slice of entries around the target (target included)
    """
    for index, entry in enumerate(entries):
        if entry is target:
            return list(entries[max(0, index - before): index + after + 1])
    return [target]


def workflow_names(entries: Sequence[LogEntry]) -> List[str]:
    """
    List the distinct workflow names appearing in a session, in first-seen order.
    """
    names: List[str] = []
    for entry in entries:
        name = entry.raw.get("workflow")
        if name and name not in names:
            names.append(name)
    return names


def entry_message(entry: LogEntry) -> str:
    """
    Best human-readable message for an entry, falling back to its event name.
    """
    raw = entry.raw
    for key in ("error", "message", "reason", "detail", "exception"):
        value = raw.get(key)
        if value:
            return str(value)
    return entry.event


def entry_context_fields(entry: LogEntry) -> str:
    """
    Render the structured payload of an entry as `key=value` pairs, skipping
    the fields already shown as timestamp / level / event / message.
    """
    skip = {"timestamp", "level", "event", "logger", "error", "message", "reason"}
    parts = [
        f"{key}={value}"
        for key, value in entry.raw.items()
        if key not in skip and value is not None
    ]
    return "  ".join(parts)


def format_entry_json(entry: LogEntry) -> str:
    """Pretty-print the full raw payload of an entry."""
    return json.dumps(entry.raw, indent=2, ensure_ascii=False, default=str)


def _searchable(entry: LogEntry) -> str:
    if entry.search_blob is None:
        entry.search_blob = json.dumps(
            entry.raw, ensure_ascii=False, default=str
        ).lower()
    return entry.search_blob


# ── Formatting ─────────────────────────────────────────────────────────────────

def to_local(value: Optional[datetime]) -> Optional[datetime]:
    """
    Convert a log instant to the machine's local timezone.

    Titan writes UTC. Showing that verbatim next to "the run I did after
    lunch" is how a two-hour offset turns into a wrong diagnosis.
    """
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone()


def format_time(value: Optional[datetime], fmt: str = "%H:%M:%S") -> str:
    local = to_local(value)
    return local.strftime(fmt) if local else "?"


def format_duration(seconds: Optional[float]) -> str:
    if seconds is None:
        return "—"
    if seconds < 60:
        return f"{seconds:.1f}s"
    minutes, rest = divmod(int(seconds), 60)
    if minutes < 60:
        return f"{minutes}m {rest:02d}s"
    hours, minutes = divmod(minutes, 60)
    return f"{hours}h {minutes:02d}m"


def format_file_label(info: LogFileInfo) -> str:
    """Label for a log file in the file selector."""
    tag = "current" if info.is_current else f"rotation {info.rotation_index}"
    return f"{info.path.name}  ({tag})"


def format_file_description(info: LogFileInfo) -> str:
    """Description line for a log file in the file selector."""
    return (
        f"  {info.size_mb:.1f} MB  ·  last written "
        f"{info.modified.strftime('%Y-%m-%d %H:%M:%S')}"
    )


def format_session_label(ref: SessionRef) -> str:
    """
    Format a session label for display in a selection list.

    Args:
        ref: SessionRef to format

    Returns:
        Human-readable label string, in local time
    """
    time_str = format_time(ref.start_time, "%Y-%m-%d  %H:%M:%S") if ref.start_time else "Unknown time"
    pid_str = f"  PID {ref.pid}" if ref.pid else ""
    duration = ref.duration_seconds
    duration_str = f"  {format_duration(duration)}" if duration else ""
    head_str = "  (head lost to rotation)" if ref.truncated_head else ""
    return f"{time_str}{pid_str}{duration_str}{head_str}"


def format_session_description(ref: SessionRef) -> str:
    """Description line for a session in the selection list."""
    parts = [f"{ref.entry_count} events"]
    if ref.error_count:
        parts.append(f"✖ {ref.error_count} error{'s' if ref.error_count != 1 else ''}")
    if ref.warning_count:
        parts.append(f"! {ref.warning_count} warning{'s' if ref.warning_count != 1 else ''}")
    if ref.version:
        parts.append(ref.version + (f" ({ref.mode})" if ref.mode else ""))
    if ref.spans_rotation:
        parts.append("spans " + " + ".join(p.name for p in ref.files))
    return "  " + "  ·  ".join(parts)


def format_entry_line(entry: LogEntry, *, max_width: int = 160) -> str:
    """
    One-line rendering of an entry for a context or filter listing.
    """
    icon = LEVEL_ICONS.get(entry.level, "·")
    message = entry_message(entry)
    fields = entry_context_fields(entry)
    text = f"{format_time(entry.timestamp)}  {icon}  {entry.event}"
    if message and message != entry.event:
        text += f"  —  {message}"
    if fields:
        text += f"   [{fields}]"
    return text if len(text) <= max_width else text[: max_width - 1] + "…"


# ── AI prompt ──────────────────────────────────────────────────────────────────

def build_session_evidence(analysis: SessionAnalysis, *, max_chars: int = 14000) -> str:
    """
    Render the findings of a session as Markdown evidence.

    This is what a model is shown instead of the raw log — the timeline, the
    grouped errors with the full payload of one occurrence, the warnings and
    the slow operations — and it is equally what a human pastes elsewhere.

    Args:
        analysis: SessionAnalysis to describe
        max_chars: Budget for the rendered evidence

    Returns:
        Markdown evidence, truncated to the budget
    """
    session = analysis.session
    lines: List[str] = []

    lines.append("### Session")
    lines.append(f"- Started: {format_time(session.start_time, '%Y-%m-%d %H:%M:%S')} (local)")
    lines.append(f"- Duration: {format_duration(session.duration_seconds)}")
    if session.version:
        lines.append(f"- Titan version: {session.version} ({session.mode or 'unknown mode'})")
    lines.append(f"- Log entries: {len(session.entries)}")

    lines.append("")
    lines.append("### Workflow timeline")
    if analysis.workflows:
        for run in analysis.workflows:
            lines.append(
                f"- [{run.status}] {run.name} ({format_duration(run.duration)})"
                + (f" — failed at '{run.failed_at}'" if run.failed_at else "")
            )
            for step in run.steps:
                detail = step.error or step.message or ""
                lines.append(
                    f"    - {step.result}: {step.step_id} "
                    f"({format_duration(step.duration)}) {detail}".rstrip()
                )
    else:
        lines.append("- No workflows ran in this session.")

    # ── What broke, and what was logged while it broke ─────────────────────────
    # This section is the point of the whole report. Each failed step is shown
    # with the entries logged inside its own window, at every level, because
    # the cause is routinely an info- or debug-level line (a provider's stderr,
    # a quota flag) that no error-level summary would ever surface.
    if analysis.failed_steps:
        lines.append("")
        lines.append("### Failed steps, with what was logged during each")
        for step in analysis.failed_steps:
            lines.append("")
            lines.append(
                f"**{step.workflow} → {step.step_id}** "
                f"({format_duration(step.duration)}, plugin `{step.plugin or '?'}`)"
            )
            lines.append(f"- Reported error: {step.error or step.message or '(none)'}")
            window = _window_highlights(step)
            if window:
                lines.append("- Logged while this step was running:")
                for entry in window:
                    lines.append(
                        f"    - [{format_time(entry.timestamp)}] {entry.level} "
                        f"{entry.event}: {_compact_payload(entry)}"
                    )
            else:
                lines.append("- Nothing else was logged during this step.")

    # ── Provider activity ──────────────────────────────────────────────────────
    if analysis.provider_events:
        lines.append("")
        lines.append("### AI provider activity")
        exhausted = analysis.quota_exhausted_providers
        if exhausted:
            lines.append(
                "- Quota reported EXHAUSTED for: " + ", ".join(f"`{n}`" for n in exhausted)
            )
        for entry in analysis.provider_events[:20]:
            lines.append(
                f"- [{format_time(entry.timestamp)}] {entry.event}: {_compact_payload(entry)}"
            )

    # ── Errors, split by whether they can be to blame ──────────────────────────
    lines.append("")
    lines.append(f"### Errors ({analysis.error_entry_count} error-level entries)")

    if analysis.implicated_errors:
        lines.append("")
        lines.append("Inside a step that failed:")
        for group in analysis.implicated_errors:
            repeat = f" (x{group.count})" if group.count > 1 else ""
            lines.append(
                f"- [{format_time(group.entry.timestamp)}]{repeat} "
                f"{group.entry.event}: {group.message}"
            )
            lines.append("  payload: " + format_entry_json(group.entry).replace("\n", "\n  "))

    if analysis.unattributed_errors:
        lines.append("")
        if analysis.looks_like_test_noise:
            stamps = [
                g.entry.timestamp
                for g in analysis.unattributed_errors
                if g.entry.timestamp
            ]
            span = (max(stamps) - min(stamps)).total_seconds() if stamps else 0
            lines.append(
                f"IGNORE THESE: {len(analysis.unattributed_errors)} DIFFERENT "
                f"`*_failed` events were logged in {span:.0f}s with no workflow "
                "running. That is the signature of this project's own test suite "
                "writing into the same log file, not of anything breaking. They "
                "are not failures of this session — do not report them, do not "
                "give them a section. Event names, for reference only: "
                + ", ".join(
                    f"`{g.entry.event}`" for g in analysis.unattributed_errors[:10]
                )
            )
        else:
            lines.append("Outside any step (startup, shutdown, background):")
            for group in analysis.unattributed_errors[:15]:
                repeat = f" (x{group.count})" if group.count > 1 else ""
                lines.append(
                    f"- [{format_time(group.entry.timestamp)}]{repeat} "
                    f"{group.entry.event}: {group.message}"
                )

    if analysis.incidental_errors:
        lines.append("")
        lines.append(
            f"Also ignore: {analysis.incidental_error_count} error entries "
            f"({len(analysis.incidental_errors)} distinct) were logged inside steps "
            "that then SUCCEEDED, so they did not break this session. Event "
            "names: "
            + ", ".join(
                f"`{group.entry.event}`" for group in analysis.incidental_errors[:8]
            )
        )

    if not analysis.implicated_errors and not analysis.unattributed_errors:
        lines.append("")
        lines.append("- No error entries that could explain a failure.")

    if analysis.warnings or analysis.warnings_outside_steps:
        lines.append("")
        lines.append(f"### Warnings ({len(analysis.warnings)} distinct, during steps)")
        for group in analysis.warnings[:20]:
            repeat = f" (x{group.count})" if group.count > 1 else ""
            lines.append(f"- {group.entry.event}{repeat}: {group.message}")
        if analysis.warnings_outside_steps:
            lines.append(
                f"- Plus {analysis.warnings_outside_steps} warnings logged outside "
                "any step, from the same source as the ignorable errors above. "
                "Not part of this session's behaviour."
            )

    if analysis.slow_ops:
        lines.append("")
        lines.append(f"### Operations slower than {SLOW_THRESHOLD_SECONDS}s")
        for entry in analysis.slow_ops[:15]:
            context = entry.raw.get("workflow") or entry.raw.get("step_id") or ""
            lines.append(f"- {format_duration(_duration_of(entry))}  {entry.event}  {context}")

    evidence = "\n".join(lines)
    if len(evidence) > max_chars:
        evidence = evidence[:max_chars] + "\n… (evidence truncated)"
    return evidence


_PAYLOAD_SKIP = {
    "event", "level", "logger", "timestamp", "prompt", "prompt_first_chars",
    "prompt_last_chars", "stdout", "stdout_first_chars", "stdout_last_chars",
    "manifest",
}

# Prompt dumps: enormous, and they say nothing about why a call failed.
_PROMPT_DUMP_EVENTS = {"ai_prompt_built", "ai_prompt_full", "ai_response_full"}
_PAYLOAD_MAX = 400


def _compact_payload(entry: LogEntry) -> str:
    """
    Render an entry's payload for the evidence: the fields that explain it,
    without the megabyte-long prompt dumps.
    """
    parts = []
    for key, value in entry.raw.items():
        if key in _PAYLOAD_SKIP or value is None:
            continue
        text = str(value)
        if len(text) > 200:
            text = text[:200] + "…"
        parts.append(f"{key}={text}")
    rendered = " ".join(parts)
    return rendered[:_PAYLOAD_MAX] + ("…" if len(rendered) > _PAYLOAD_MAX else "")


def _window_highlights(step: StepRun, limit: int = 14) -> List[LogEntry]:
    """
    The entries from a failed step's window that are worth showing.

    Ranked, not truncated chronologically: a provider's quota flag can be the
    fifth of two hundred debug lines, and taking "the last N" would drop it.
    """
    scored: List[Tuple[int, int, LogEntry]] = []
    for position, entry in enumerate(step.entries):
        raw = entry.raw
        if entry.event in _PROMPT_DUMP_EVENTS and entry.level not in ERROR_LEVELS:
            continue
        score = 0
        if raw.get("quota_exhausted") is True or raw.get("timed_out") is True:
            score = 100
        elif entry.level in ERROR_LEVELS:
            score = 80
        elif isinstance(raw.get("exit_code"), int) and raw["exit_code"] != 0:
            score = 70
        elif any(key in raw for key in ("stderr", "stderr_first_chars")):
            score = 60
        elif entry.event.endswith("_failed") or entry.event.endswith("_crashed"):
            score = 50
        elif entry.level == "warning":
            score = 40
        elif entry.event.startswith("ai_") or "cli" in raw:
            score = 20
        if score:
            scored.append((-score, position, entry))
    scored.sort()
    chosen = [item[2] for item in scored[:limit]]
    return sorted(chosen, key=lambda e: step.entries.index(e))


def build_diagnosis_prompt(analysis: SessionAnalysis, *, max_chars: int = 14000) -> str:
    """
    Build the prompt asking a model to diagnose a session.

    Args:
        analysis: SessionAnalysis to describe
        max_chars: Budget for the evidence section

    Returns:
        The prompt string
    """
    evidence = build_session_evidence(analysis, max_chars=max_chars)
    return (
        "You are diagnosing a session of Titan CLI, a terminal tool that runs "
        "YAML-defined workflows over git, GitHub, Jira and Slack.\n\n"
        "Below is a structured extract of one session's log.\n\n"
        f"{evidence}\n\n"
        "Your job is to name the CAUSE, not to summarize the log. The user can "
        "already see the timeline and the error counts; what they cannot see is "
        "why it broke.\n\n"
        "How to find it:\n"
        "- Start from the failed steps and read what was logged inside each one. "
        "The cause is usually there, at info or debug level, not in the error "
        "list.\n"
        "- An external tool that reported a spent quota, a timeout, a non-zero "
        "exit code or an authentication failure IS the cause. Say so directly, "
        "and name the tool and the limit it hit. Do not describe such a failure "
        "as merely 'the step produced no output'.\n"
        "- A step that failed and left later steps with nothing to do explains "
        "those later steps. Report the first cause once; do not give each "
        "downstream skip its own explanation.\n"
        "- The evidence marks some errors as logged inside steps that succeeded. "
        "Those are noise from a test suite. Never present them as failures, and "
        "do not spend a section on them.\n\n"
        "Write it in Markdown, in this order:\n"
        "1. **Root cause** — ONE sentence, first thing in the answer, naming what "
        "broke and why. If the evidence genuinely does not identify a cause, say "
        "exactly that in that one sentence instead of guessing.\n"
        "2. **What happened** — two or three sentences on what the user was doing "
        "and how the session ended.\n"
        "3. **Consequences** — only the failures that are not already explained by "
        "the root cause, one line each.\n"
        "4. **What to do** — concrete next steps, most useful first. When the "
        "cause is an exhausted or misconfigured provider, the first step is the "
        "specific fix (wait for the reset, or route that task to another "
        "provider in AI Configuration).\n\n"
        "Be brief: this must fit on one screen. Do not invent log lines, file "
        "paths or error messages that are not in the evidence, and do not repeat "
        "the timeline back."
    )


def build_report_document(
    analysis: SessionAnalysis,
    diagnosis: Optional[str] = None,
    *,
    max_chars: int = 14000,
) -> str:
    """
    Build a self-contained Markdown report of the session.

    Written to be pasted somewhere else — another assistant, an issue, a
    message to a colleague — so it carries the evidence even when the
    diagnosis is missing, and states which log files it came from.

    Args:
        analysis: SessionAnalysis to report on
        diagnosis: The AI diagnosis, when one was generated
        max_chars: Budget for the evidence section

    Returns:
        The report as Markdown
    """
    session = analysis.session
    started = format_time(session.start_time, "%Y-%m-%d %H:%M:%S")
    sources = ", ".join(path.name for path in session.ref.files) or "unknown"

    parts = [
        f"# Titan session report — {started} (local)",
        "",
        f"Source: `{sources}`"
        + (f" · PID {session.pid}" if session.pid else "")
        + (f" · titan {session.version}" if session.version else ""),
        "",
    ]

    if diagnosis:
        parts += ["## Diagnosis", "", diagnosis.strip(), "", "---", ""]
    else:
        parts += [
            "_No AI diagnosis was generated for this session; the evidence "
            "below is the whole report._",
            "",
        ]

    parts += ["## Evidence", "", build_session_evidence(analysis, max_chars=max_chars)]
    return "\n".join(parts) + "\n"


def default_report_path(
    session: LogSession, directory: Path = DEFAULT_REPORT_DIR
) -> Path:
    """
    Where to write a session report by default.

    Args:
        session: The session being reported on
        directory: Target directory (created by the caller)

    Returns:
        A path named after the session's start instant
    """
    start = to_local(session.start_time)
    stamp = start.strftime("%Y%m%d-%H%M%S") if start else "unknown"
    return directory / f"titan-session-{stamp}.md"


# ── Private helpers ────────────────────────────────────────────────────────────

def _parse_log_entry(raw: bytes, source: Optional[Path] = None) -> Optional[LogEntry]:
    data = _loads(raw)
    if data is None:
        return None

    timestamp = None
    raw_timestamp = data.get("timestamp")
    if isinstance(raw_timestamp, str):
        timestamp = _parse_iso(raw_timestamp)

    return LogEntry(
        timestamp=timestamp,
        level=str(data.get("level", "unknown")),
        event=str(data.get("event", "")),
        raw=data,
        source=source,
    )


def _loads(raw: bytes) -> Optional[Dict[str, Any]]:
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, ValueError, UnicodeDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _parse_iso(value: str) -> Optional[datetime]:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    # structlog writes UTC; a bare instant would otherwise be compared against
    # aware ones and raise.
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _extract_timestamp(raw: bytes) -> Optional[datetime]:
    marker = b'"timestamp": "'
    start = raw.find(marker)
    if start == -1:
        return None
    start += len(marker)
    end = raw.find(b'"', start)
    if end == -1:
        return None
    try:
        return _parse_iso(raw[start:end].decode("ascii"))
    except UnicodeDecodeError:
        return None


_BANNER_TIME = re.compile(
    r"SESSION START\s+(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})(?:\s+([A-Z]{2,5}))?"
)


def _parse_banner_time(line: str) -> Optional[datetime]:
    match = _BANNER_TIME.search(line)
    if not match:
        return None
    try:
        parsed = datetime.strptime(match.group(1), "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None
    # The banner states its zone ("... 10:02:45 UTC"). Dropping that suffix is
    # what made every session render two hours off in CEST.
    zone = match.group(2)
    if zone in ("UTC", "GMT", "Z"):
        return parsed.replace(tzinfo=timezone.utc)
    # No zone stated: the banner was written by a build that logged local time.
    return parsed.astimezone()


def _parse_banner_pid(line: str) -> Optional[int]:
    match = re.search(r"PID\s+(\d+)", line)
    if not match:
        return None
    try:
        return int(match.group(1))
    except ValueError:
        return None


def _is_separator(raw: bytes) -> bool:
    return raw.startswith("─".encode("utf-8")) or raw.startswith(b"-" * 10)


__all__ = [
    # Models
    "LogFileInfo",
    "LogEntry",
    "SessionSegment",
    "SessionRef",
    "LogSession",
    "StepRun",
    "WorkflowRun",
    "EntryGroup",
    "SessionAnalysis",
    # Constants
    "DEFAULT_LOG_DIR",
    "DEFAULT_LOG_NAME",
    "DEFAULT_REPORT_DIR",
    "SLOW_THRESHOLD_SECONDS",
    "ERROR_LEVELS",
    "ENGINE_TIMELINE_EVENTS",
    "STEP_RESULT_ICONS",
    "STEP_RESULT_LEGEND",
    "WORKFLOW_STATUS_ICONS",
    "LEVEL_ICONS",
    # Discovery
    "discover_log_files",
    "chronological_paths",
    # Reading
    "index_sessions",
    "load_session",
    # Analysis
    "analyze_session",
    "group_entries",
    # Exploration
    "filter_entries",
    "entries_around",
    "workflow_names",
    "entry_message",
    "entry_context_fields",
    "format_entry_json",
    # Formatting
    "to_local",
    "format_time",
    "format_duration",
    "format_file_label",
    "format_file_description",
    "format_session_label",
    "format_session_description",
    "format_entry_line",
    # AI and export
    "build_session_evidence",
    "build_diagnosis_prompt",
    "build_report_document",
    "default_report_path",
]
