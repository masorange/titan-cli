"""
Workflow Run Profiling Operations

A focused picture of how ONE run of ANY workflow actually worked.

Nothing here knows what a workflow does. The shape of the report is derived
from the log itself, which is possible because structlog entries are
key/value: a field that repeats with a varying id is a per-item table, a
number is a quantity worth tracking across the run, a boolean that came out
True is a flag someone chose to record, a pair of `*_actual_*` and
`*_target_*` fields is a budget. Give it a Review PR run and the batches
appear; give it a Slack or a merge workflow and whatever that one repeats
appears instead.

The alternative — a hand-written report per workflow — goes stale the moment
someone adds a step, and never covers the workflow you happen to care about
today.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .log_operations import (
    ENGINE_TIMELINE_EVENTS,
    LogEntry,
    StepRun,
    WorkflowRun,
    format_duration,
    format_time,
)

# Payload dumps and pure plumbing: large, and they describe the transport
# rather than the work.
_SKIP_EVENTS = {
    "ai_prompt_built",
    "ai_prompt_full",
    "ai_response_full",
    "ai_response_received",
}
_SKIP_FIELDS = {
    "event", "level", "logger", "timestamp", "prompt", "stdout", "stderr",
    "prompt_first_chars", "prompt_last_chars", "stdout_first_chars",
    "stdout_last_chars", "stderr_first_chars", "stderr_last_chars",
    "manifest", "result_type",
}

# A value longer than this is prose, not a metric.
_MAX_VALUE_CHARS = 60
_MAX_TABLE_ROWS = 30
_MAX_LIST_SAMPLE = 6

# Name fragments that mark an integer as a quantity of work — the numbers a
# funnel is made of. Matched as substrings of the field name.
_COUNT_HINTS = (
    "count", "files", "candidates", "excluded", "total", "items", "entries",
    "attempted", "succeeded", "failed", "removed", "added", "batches",
    "findings", "comments", "lines", "hunks", "steps", "messages",
)

# Below this, a duration ratio is rounding noise, not a regression.
_RATIO_FLOOR_SECONDS = 1.0

# Fields that name the thing a row is about, best first.
_IDENTITY_RANK = {"path": 0, "file": 0, "batch_id": 0, "id": 0, "name": 0, "channel": 0}

# Transport, not work: one row per HTTP or git call buries the two tables that
# describe what the workflow actually did. Collapsed to a count and a total.
_PLUMBING_SUFFIXES = ("_command_ok", "_command_failed")
_PLUMBING_EVENTS = {"graphql_ok", "graphql_failed"}

# Some log calls bake their values into the event name ("found file: a/b.py",
# "path=%s count=%s"). Each value then looks like a distinct event and floods
# the report with one row per file. They are grouped under the stem before the
# colon and counted — the values are still in the entries, just not pretending
# to be event names.
_MESSAGE_EVENT_MARKERS = (": ", "=", "%s")

_BUDGET_ACTUAL = "actual"
_BUDGET_LIMITS = ("target", "budget", "max", "limit")


@dataclass
class ItemTable:
    """A repeated event rendered one row per occurrence."""
    event: str
    columns: List[str]
    rows: List[List[str]]

    @property
    def occurrences(self) -> int:
        return len(self.rows)


@dataclass
class Budget:
    label: str
    actual: float
    limit: float

    @property
    def used_pct(self) -> float:
        return (self.actual / self.limit * 100) if self.limit else 0.0


@dataclass
class StepProfile:
    step: StepRun
    tables: List[ItemTable] = field(default_factory=list)
    metrics: List[Tuple[str, str]] = field(default_factory=list)
    flags: List[str] = field(default_factory=list)
    budgets: List[Budget] = field(default_factory=list)
    lists: List[Tuple[str, int, List[str]]] = field(default_factory=list)
    event_count: int = 0

    @property
    def has_content(self) -> bool:
        return bool(self.tables or self.metrics or self.flags or self.budgets or self.lists)


@dataclass
class FunnelPoint:
    step_id: str
    event: str
    field_name: str
    value: int
    timestamp: Optional[datetime]


@dataclass
class WorkflowRunProfile:
    run: WorkflowRun
    steps: List[StepProfile]
    funnel: List[FunnelPoint]

    @property
    def profiled_steps(self) -> List[StepProfile]:
        return [profile for profile in self.steps if profile.has_content]


def profile_workflow_run(run: WorkflowRun) -> WorkflowRunProfile:
    """
    Build a focused picture of one workflow run.

    Args:
        run: The WorkflowRun to profile, with its steps' entries attached

    Returns:
        WorkflowRunProfile with per-step tables, metrics, flags and budgets,
        plus the run's quantities in time order
    """
    steps = [_profile_step(step) for step in run.steps]
    return WorkflowRunProfile(run=run, steps=steps, funnel=_funnel(steps))


def _profile_step(step: StepRun) -> StepProfile:
    entries = [
        entry for entry in step.entries
        if entry.event not in _SKIP_EVENTS and entry.event not in ENGINE_TIMELINE_EVENTS
    ]
    profile = StepProfile(step=step, event_count=len(entries))

    # Budgets are read from EVERY entry, including the prompt dumps skipped
    # above: those carry the payload that is too big to show and the
    # actual-vs-target pair that is the most useful number in it.
    for entry in step.entries:
        budget = _budget_from(entry.raw)
        if budget is not None:
            profile.budgets.append(budget)

    by_event: Dict[str, List[LogEntry]] = {}
    for entry in entries:
        by_event.setdefault(_event_key(entry.event), []).append(entry)

    for event, occurrences in by_event.items():
        table = _item_table(event, occurrences)
        if table is not None:
            profile.tables.append(table)
            continue

        if len(occurrences) > 1:
            # Repeated but indistinguishable: a count says everything a list
            # of identical rows would, plus the time they added up to.
            total = sum(
                value for entry in occurrences
                if isinstance(value := entry.raw.get("duration"), (int, float))
            )
            suffix = f" ({format_duration(total)} total)" if total else ""
            kind = "messages" if _event_key(occurrences[0].event) != occurrences[0].event else "calls"
            profile.metrics.append((event, f"{len(occurrences)} {kind}{suffix}"))

        _collect_fields(occurrences[0], profile)

    profile.budgets = _dedupe_budgets(profile.budgets)
    profile.metrics = _dedupe_pairs(profile.metrics)
    profile.flags = list(dict.fromkeys(profile.flags))
    return profile


def _item_table(event: str, occurrences: Sequence[LogEntry]) -> Optional[ItemTable]:
    """
    Render an event that repeats within a step as one row per occurrence.

    Requires an id-like field that actually varies: without it, a repeat is
    just the same line logged twice and a table would say nothing a count
    does not.
    """
    if len(occurrences) < 2 or _is_plumbing(event):
        return None

    # What identifies the item has to be a TEXT field that varies: a batch id,
    # a path, a channel. Requiring `*_id` missed every per-file event, and
    # accepting any varying field would turn seven git calls that differ only
    # in their duration into a seven-row table of durations.
    def varies(key: str) -> bool:
        return len({_render(entry.raw.get(key)) for entry in occurrences}) > 1

    def is_text(key: str) -> bool:
        return all(
            isinstance(entry.raw.get(key), str) or entry.raw.get(key) is None
            for entry in occurrences
        )

    ranked = sorted(
        (
            key for key in occurrences[0].raw
            if key not in _SKIP_FIELDS and is_text(key) and varies(key)
        ),
        # An explicit identifier beats an incidental string like a mode or a
        # subcommand. Length is NOT a criterion here: dropping `path` because
        # one file sits in a deep directory leaves a table of read modes with
        # nothing to attach them to, which is worse than a truncated path.
        key=lambda key: (_IDENTITY_RANK.get(key, 1 if key.endswith("_id") else 2), key),
    )
    varying_id = next(iter(ranked), None)
    if varying_id is None:
        return None

    # Columns: the id first, then every field that differs between rows.
    candidates = [
        key for key in occurrences[0].raw
        if key not in _SKIP_FIELDS and key != varying_id
    ]
    columns = [varying_id] + [
        key for key in candidates
        if len({_render(entry.raw.get(key)) for entry in occurrences}) > 1
        and all(len(_render(entry.raw.get(key))) <= _MAX_VALUE_CHARS for entry in occurrences)
    ]

    rows = [
        [_truncate(_render(entry.raw.get(column))) for column in columns]
        for entry in occurrences[:_MAX_TABLE_ROWS]
    ]
    return ItemTable(event=event, columns=columns, rows=rows)


def _event_key(event: str) -> str:
    """Group formatted log messages under the stem they share."""
    if any(marker in event for marker in _MESSAGE_EVENT_MARKERS):
        return event.split(":", 1)[0].strip() or event
    return event


def _is_plumbing(event: str) -> bool:
    return event in _PLUMBING_EVENTS or event.endswith(_PLUMBING_SUFFIXES)


def _truncate(text: str) -> str:
    if len(text) <= _MAX_VALUE_CHARS:
        return text
    # Keep the tail of a path: the filename identifies it, the parent dirs do not.
    return "…" + text[-(_MAX_VALUE_CHARS - 1):]


def _collect_fields(entry: LogEntry, profile: StepProfile) -> None:
    raw = entry.raw
    for key, value in raw.items():
        if key in _SKIP_FIELDS or value is None:
            continue

        if isinstance(value, bool):
            if value:
                profile.flags.append(f"{key} ({entry.event})")
            continue

        if isinstance(value, (int, float)):
            profile.metrics.append((f"{entry.event}.{key}", _render(value)))
            continue

        if isinstance(value, (list, tuple)):
            sample = [_render(item) for item in value[:_MAX_LIST_SAMPLE]]
            profile.lists.append((f"{entry.event}.{key}", len(value), sample))
            continue

        text = _render(value)
        if len(text) <= _MAX_VALUE_CHARS:
            profile.metrics.append((f"{entry.event}.{key}", text))

    budget = _budget_from(raw)
    if budget is not None:
        profile.budgets.append(budget)


def _budget_from(raw: Dict[str, Any]) -> Optional[Budget]:
    """
    Find an `*_actual_*` / `*_target_*` pair sharing a stem in one payload.

    Only within a single entry: correlating a limit logged by one step with a
    usage logged by another would be guessing at a relationship the log does
    not state.
    """
    for key, value in raw.items():
        if _BUDGET_ACTUAL not in key or not isinstance(value, (int, float)):
            continue
        stem = key.split(_BUDGET_ACTUAL)[0]
        for other, limit in raw.items():
            if other == key or not isinstance(limit, (int, float)) or not limit:
                continue
            if other.startswith(stem) and any(word in other for word in _BUDGET_LIMITS):
                return Budget(label=f"{stem.rstrip('_')} ({key} / {other})",
                              actual=float(value), limit=float(limit))
    return None


def _funnel(steps: Sequence[StepProfile]) -> List[FunnelPoint]:
    """
    The run's quantities in the order they were logged.

    Reading them top to bottom is what shows work being lost: files that
    became candidates, candidates that reached a batch, results that survived
    deduplication.
    """
    points: List[FunnelPoint] = []
    for profile in steps:
        for entry in profile.step.entries:
            if entry.event in _SKIP_EVENTS or entry.event in ENGINE_TIMELINE_EVENTS:
                continue
            for key, value in entry.raw.items():
                if key in _SKIP_FIELDS or isinstance(value, bool):
                    continue
                if not isinstance(value, int):
                    continue
                if not any(hint in key for hint in _COUNT_HINTS):
                    continue
                points.append(FunnelPoint(
                    step_id=profile.step.step_id,
                    event=entry.event,
                    field_name=key,
                    value=value,
                    timestamp=entry.timestamp,
                ))
    return points


def format_run_header(run: WorkflowRun) -> str:
    """One line naming the run being profiled."""
    return (
        f"{run.name} — {run.status_label} · started {format_time(run.started_at)} "
        f"· {format_duration(run.duration)} · {run.step_summary}"
    )


def _render(value: Any) -> str:
    if isinstance(value, float):
        return f"{value:g}"
    if isinstance(value, bool):
        return "yes" if value else "no"
    text = str(value)
    return text if len(text) <= 200 else text[:200] + "…"


def _dedupe_pairs(pairs: Sequence[Tuple[str, str]]) -> List[Tuple[str, str]]:
    seen: Dict[str, str] = {}
    for key, value in pairs:
        seen.setdefault(key, value)
    return list(seen.items())


def _dedupe_budgets(budgets: Sequence[Budget]) -> List[Budget]:
    seen: Dict[str, Budget] = {}
    for budget in budgets:
        seen.setdefault(budget.label, budget)
    return list(seen.values())


# ── Interpreters ───────────────────────────────────────────────────────────────
#
# Data, not code. An interpreter never extracts anything — the structurer above
# already did that — it only NAMES what was found and says which numbers form
# this workflow's funnel. Adding a workflow is adding an entry here; a workflow
# with no entry still gets the generic report, just with raw field names.
#
# Everything is looked up leniently: a field that stops being logged makes its
# row disappear, it never raises. That is what keeps this from going stale the
# way a hand-written report per workflow does.

@dataclass
class FunnelStage:
    label: str
    value: int
    field_name: str
    # The things behind the number, when the log names them. A count alone
    # says work happened; the identities say whether it was the right work.
    items: List[str] = field(default_factory=list)
    items_field: Optional[str] = None

    @property
    def items_complete(self) -> bool:
        """Whether the named items account for the whole count."""
        return bool(self.items) and len(self.items) == self.value


@dataclass
class Interpretation:
    workflow: str
    known: bool
    stages: List[FunnelStage] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)


# event.field → human label, per workflow. The order of the funnel entries is
# the order of the stages.
INTERPRETERS: Dict[str, Dict[str, Any]] = {
    "Review PR": {
        # (count field, label, field holding the identities behind it)
        "funnel": [
            ("review_config_applied_to_pr.manifest_files", "Files changed in the PR", None),
            (
                "review_config_applied_to_pr.candidate_files",
                "Files selected for review",
                "review_candidates_scored.candidate_paths",
            ),
            (
                "review_candidates_scored.excluded",
                "Files excluded by scoring",
                "review_candidates_scored.excluded_files",
            ),
            ("review_context_summary.comments_in_context", "Existing comments in context", None),
            ("findings_deduplicated.deduped_findings_count", "Findings after dedup", None),
            (
                "findings_deduplicated.findings_removed_due_to_existing_threads",
                "Findings dropped (already commented)",
                None,
            ),
        ],
        "labels": {
            "file_context_resolved": "Files the reviewer actually read",
            "findings_batch_adapter_call": "Review batches sent to the AI",
            "review_strategy_selected.strategy": "Review strategy",
            "review_strategy_selected.size_class": "PR size class",
        },
        "thresholds": [
            ("prompt", 90, "The prompt budget is nearly full — files may be arriving trimmed"),
        ],
    },
}


def interpret_run(profile: WorkflowRunProfile) -> Interpretation:
    """
    Name what the structurer found, using this workflow's interpreter.

    Args:
        profile: The profiled run

    Returns:
        Interpretation — named funnel stages and notes. `known` is False when
        no interpreter exists, in which case the generic report stands alone.
    """
    spec = INTERPRETERS.get(profile.run.name)
    interpretation = Interpretation(workflow=profile.run.name, known=spec is not None)
    if spec is None:
        return interpretation

    observed = {
        f"{point.event}.{point.field_name}": point.value for point in profile.funnel
    }
    named_lists = _collect_lists(profile)

    for key, label, items_key in spec.get("funnel", []):
        if key not in observed:
            continue
        value = observed[key]
        items = list(named_lists.get(items_key, [])) if items_key else []
        if not items:
            items = _infer_items(named_lists, key, value)
        interpretation.stages.append(
            FunnelStage(
                label=label,
                value=value,
                field_name=key,
                items=items,
                items_field=items_key,
            )
        )

    for stem, limit_pct, note in spec.get("thresholds", []):
        for step_profile in profile.steps:
            for budget in step_profile.budgets:
                if budget.label.startswith(stem) and budget.used_pct >= limit_pct:
                    # Name the step and show the raw numbers: an unattributed
                    # percentage reads as if it were about the tool doing the
                    # auditing rather than the run being audited.
                    interpretation.notes.append(
                        f"{step_profile.step.step_id}: {note} "
                        f"({budget.actual:,.0f} of {budget.limit:,.0f} chars, "
                        f"{budget.used_pct:.0f}%)"
                    )
    return interpretation


def _collect_lists(profile: WorkflowRunProfile) -> Dict[str, List[str]]:
    """Every list-valued field in the run, keyed `event.field`."""
    found: Dict[str, List[str]] = {}
    for step_profile in profile.steps:
        for entry in step_profile.step.entries:
            for key, value in entry.raw.items():
                if isinstance(value, (list, tuple)) and value:
                    found.setdefault(
                        f"{entry.event}.{key}", [_render(item) for item in value]
                    )
    return found


def _infer_items(
    named_lists: Dict[str, List[str]], count_key: str, value: int
) -> List[str]:
    """
    Guess the identities behind a count when the interpreter did not name them.

    Only accepted when the match is unambiguous: the list lives in the same
    event and has exactly as many items as the count. A list that is one short
    because it was logged as a top-5 sample would otherwise be presented as
    the whole set.
    """
    if value <= 0:
        return []
    event = count_key.rsplit(".", 1)[0]
    matches = [
        items for key, items in named_lists.items()
        if key.startswith(f"{event}.") and len(items) == value
    ]
    return list(matches[0]) if len(matches) == 1 else []


def label_for(workflow: str, key: str) -> Optional[str]:
    """Human label an interpreter gives to an event or field, if any."""
    spec = INTERPRETERS.get(workflow)
    return spec.get("labels", {}).get(key) if spec else None


# ── History ────────────────────────────────────────────────────────────────────

@dataclass
class StepStats:
    step_id: str
    runs: int
    durations: List[float]
    failures: int

    @property
    def median(self) -> Optional[float]:
        if not self.durations:
            return None
        ordered = sorted(self.durations)
        middle = len(ordered) // 2
        if len(ordered) % 2:
            return ordered[middle]
        return (ordered[middle - 1] + ordered[middle]) / 2

    @property
    def worst(self) -> Optional[float]:
        return max(self.durations) if self.durations else None

    @property
    def failure_pct(self) -> float:
        return (self.failures / self.runs * 100) if self.runs else 0.0


@dataclass
class RunHistory:
    workflow: str
    runs: int
    steps: Dict[str, StepStats] = field(default_factory=dict)

    def compare(self, step: StepRun) -> Optional[StepStats]:
        return self.steps.get(step.step_id)


def build_run_history(runs: Sequence[WorkflowRun], exclude: WorkflowRun) -> RunHistory:
    """
    Aggregate previous runs of the same workflow, for comparison.

    Args:
        runs: Every run found, of any workflow
        exclude: The run being audited, kept out of its own baseline

    Returns:
        RunHistory over the other runs of the same workflow
    """
    history = RunHistory(workflow=exclude.name, runs=0)
    for run in runs:
        if run.name != exclude.name or run is exclude:
            continue
        history.runs += 1
        for step in run.steps:
            stats = history.steps.get(step.step_id)
            if stats is None:
                stats = StepStats(step_id=step.step_id, runs=0, durations=[], failures=0)
                history.steps[step.step_id] = stats
            stats.runs += 1
            if isinstance(step.duration, (int, float)):
                stats.durations.append(float(step.duration))
            if step.failed:
                stats.failures += 1
    return history


def format_comparison(step: StepRun, stats: Optional[StepStats]) -> str:
    """One-line comparison of a step against its own history."""
    if stats is None or not stats.runs:
        return "no history"
    parts = []
    median = stats.median
    if median is not None:
        parts.append(f"median {format_duration(median)}")
        # Only compare speeds once there is a real duration to compare. Below
        # a second, the ratio is measuring rounding: 0.02s against 0.24s is a
        # "12× speedup" that means nothing.
        if (
            isinstance(step.duration, (int, float))
            and max(step.duration, median) >= _RATIO_FLOOR_SECONDS
            and median > 0
        ):
            ratio = step.duration / median
            if ratio >= 2:
                parts.append(f"⚠ {ratio:.1f}× slower than usual")
            elif ratio <= 0.5:
                parts.append(f"{1 / ratio:.1f}× faster than usual")
    if stats.failures:
        parts.append(f"{stats.failures}/{stats.runs} runs failed here")
    return f"n={stats.runs} · " + " · ".join(parts)


# ── Run inventory ──────────────────────────────────────────────────────────────
#
# You know which workflow you want to look at; you do not know which session it
# ran in. So the entry point is the workflow, and sessions are an implementation
# detail of where a run happens to live.
#
# Same two-phase shape as session reading: the inventory keeps each run's shape
# (steps, results, durations) but DROPS its entries, so listing every run of
# every workflow costs a fraction of a second and a trivial amount of memory.
# The chosen run is re-read in full.

@dataclass
class RunRef:
    """Where a run lives, and enough of it to choose from a list."""
    run: WorkflowRun          # entries stripped
    session: "Any"            # SessionRef
    index: int                # position among the session's runs

    @property
    def name(self) -> str:
        return self.run.name or "(unnamed workflow)"

    @property
    def failed_step(self) -> Optional[str]:
        return next((s.step_id for s in self.run.steps if s.failed), None)


@dataclass
class WorkflowSummary:
    name: str
    runs: int
    failed: int
    last_seen: Optional[datetime]
    total_steps: int

    @property
    def failure_pct(self) -> float:
        return (self.failed / self.runs * 100) if self.runs else 0.0


def inventory_runs(paths: Sequence[Any]) -> List[RunRef]:
    """
    Every workflow run in the given log files, oldest first, without entries.

    Args:
        paths: Log file paths, oldest first

    Returns:
        List of RunRef — cheap to build, enough to render both selectors and
        to compute a historical baseline
    """
    from .log_operations import analyze_session, index_sessions, load_session

    refs: List[RunRef] = []
    for session_ref in index_sessions(paths):
        try:
            analysis = analyze_session(load_session(session_ref))
        except OSError:
            continue
        for index, run in enumerate(analysis.workflows):
            for step in run.steps:
                step.entries = []       # the whole point: keep shape, drop weight
            refs.append(RunRef(run=run, session=session_ref, index=index))
    return refs


def load_run(ref: RunRef) -> Optional[WorkflowRun]:
    """
    Re-read one run in full, with every step's entries attached.

    Args:
        ref: The RunRef chosen from the inventory

    Returns:
        The WorkflowRun, or None if the log no longer yields it
    """
    from .log_operations import analyze_session, load_session

    runs = analyze_session(load_session(ref.session)).workflows
    if ref.index < len(runs):
        return runs[ref.index]
    # Rotation trimmed the file since the inventory was built; fall back to
    # matching by name rather than returning the wrong run.
    return next((run for run in runs if run.name == ref.run.name), None)


def summarize_workflows(refs: Sequence[RunRef]) -> List[WorkflowSummary]:
    """
    Group an inventory by workflow, most recently used first.

    Args:
        refs: The run inventory

    Returns:
        One WorkflowSummary per distinct workflow name
    """
    grouped: Dict[str, List[RunRef]] = {}
    for ref in refs:
        grouped.setdefault(ref.name, []).append(ref)

    summaries = [
        WorkflowSummary(
            name=name,
            runs=len(group),
            failed=sum(
                1 for item in group
                if item.run.status == "failed" or item.failed_step
            ),
            last_seen=max(
                (item.run.started_at for item in group if item.run.started_at),
                default=None,
            ),
            total_steps=sum(len(item.run.steps) for item in group),
        )
        for name, group in grouped.items()
    ]
    summaries.sort(key=lambda s: (s.last_seen is None, s.last_seen), reverse=True)
    return summaries


def format_run_choice(ref: RunRef) -> str:
    """Description line for one run in the run selector."""
    run = ref.run
    parts = [run.status_label, run.step_summary]
    if run.duration is not None:
        parts.insert(1, format_duration(run.duration))
    if ref.failed_step:
        parts.append(f"failed at '{ref.failed_step}'")
    session = ref.session
    if getattr(session, "pid", None):
        parts.append(f"PID {session.pid}")
    return "  ·  " + "  ·  ".join(parts)


# ── AI assessment ──────────────────────────────────────────────────────────────

def build_assessment_prompt(
    profile: WorkflowRunProfile,
    interpretation: Interpretation,
    history: RunHistory,
    *,
    max_chars: int = 10000,
) -> str:
    """
    Build the prompt asking a model how well this run worked.

    A different question from the failure diagnosis: nothing here has
    necessarily gone wrong. What is wanted is a judgement about the quality
    of the work — whether the right things were covered, whether a step is
    being starved or over-fed — and that is precisely what a threshold cannot
    compute.
    """
    lines: List[str] = ["### Run", format_run_header(profile.run), ""]

    if interpretation.stages:
        lines.append("### What the run processed")
        for stage in interpretation.stages:
            lines.append(f"- {stage.label}: {stage.value}")
        lines.append("")
    elif profile.funnel:
        lines.append("### Quantities logged, in order")
        for point in profile.funnel[:25]:
            lines.append(f"- {point.step_id}: {point.event}.{point.field_name} = {point.value}")
        lines.append("")

    if interpretation.notes:
        lines.append("### Flagged automatically")
        lines += [f"- {note}" for note in interpretation.notes]
        lines.append("")

    lines.append("### Steps")
    for step_profile in profile.profiled_steps:
        step = step_profile.step
        comparison = format_comparison(step, history.compare(step))
        lines.append(
            f"- **{step.step_id}** ({step.result}, {format_duration(step.duration)}) "
            f"— history: {comparison}"
        )
        for budget in step_profile.budgets:
            lines.append(
                f"    - budget {budget.label}: {budget.actual:.0f}/{budget.limit:.0f} "
                f"= {budget.used_pct:.0f}%"
            )
        for flag in step_profile.flags[:6]:
            lines.append(f"    - flag: {flag}")
        for table in step_profile.tables:
            label = label_for(profile.run.name, table.event) or table.event
            lines.append(f"    - {label} — {table.occurrences} items, "
                         f"columns: {', '.join(table.columns)}")
            for row in table.rows[:8]:
                lines.append("        · " + " | ".join(row))
        for name, size, sample in step_profile.lists[:4]:
            lines.append(f"    - {name}: {size} items, e.g. {', '.join(sample[:4])}")

    evidence = "\n".join(lines)
    if len(evidence) > max_chars:
        evidence = evidence[:max_chars] + "\n… (truncated)"

    known = (
        "The stage labels above come from a curated interpreter for this "
        "workflow, so they mean what they say."
        if interpretation.known
        else "There is no curated interpreter for this workflow, so the field "
        "names below are raw. Do not guess at the meaning of a field whose "
        "name is not self-explanatory — say it is unclear instead."
    )

    return (
        "You are assessing how well one run of a Titan CLI workflow did its "
        "job. This is NOT a failure diagnosis: the run may have completed "
        f"fine. {known}\n\n"
        f"{evidence}\n\n"
        "Answer in Markdown, briefly:\n"
        "1. **How it went** — one or two sentences.\n"
        "2. **Worth improving** — the specific things in THIS run that look "
        "suboptimal: work that was skipped or trimmed, a budget nearly full or "
        "mostly unused, a step far off its historical time, items processed "
        "with less context than their siblings. One line each, each tied to a "
        "number above.\n"
        "3. **Nothing to say about** — if the evidence does not support a "
        "judgement on coverage or quality, say so plainly in one line and stop.\n\n"
        "Do not restate the step list, do not praise, and never infer that "
        "something was done well merely because no error was logged."
    )


__all__ = [
    "RunRef",
    "WorkflowSummary",
    "inventory_runs",
    "load_run",
    "summarize_workflows",
    "format_run_choice",
    "build_assessment_prompt",
    "ItemTable",
    "Budget",
    "StepProfile",
    "FunnelPoint",
    "WorkflowRunProfile",
    "profile_workflow_run",
    "format_run_header",
    "FunnelStage",
    "Interpretation",
    "INTERPRETERS",
    "interpret_run",
    "label_for",
    "StepStats",
    "RunHistory",
    "build_run_history",
    "format_comparison",
]
