"""
Step: explore_log_session

Interactive digging through the parsed session: read an error with the raw
lines that surround it, filter entries by level / workflow / text, or follow
one workflow end to end.

A structured summary says a step failed. What it failed on is almost always
in the twenty debug lines before the failure, which is what this step exists
to show.
"""

from typing import List, Optional

from titan_cli.engine import WorkflowContext, WorkflowResult, Success, Error, Skip
from titan_cli.ui.tui.widgets import (
    ChoiceOption,
    MultilineInput,
    OptionItem,
    Table,
)

from operations import (
    ERROR_LEVELS,
    LogEntry,
    entries_around,
    entry_message,
    filter_entries,
    format_entry_json,
    format_entry_line,
    format_time,
    workflow_names,
)

_MAX_LISTED = 200
_MAX_PICKABLE = 60


def explore_log_session(ctx: WorkflowContext) -> WorkflowResult:
    """
    Browse the raw entries of the analyzed session.

    Inputs:
        log_session (LogSession): From analyze_log_session

    Returns:
        Success when the user looked at something, Skip when they went
        straight out.
    """
    if not ctx.textual:
        return Error("Textual UI context is not available for this step.")

    ctx.textual.begin_step("Explore Log")

    session = ctx.get("log_session")
    if not session:
        ctx.textual.end_step("error")
        return Error("No session in context. Run analyze_log_session first.")

    entries: List[LogEntry] = session.entries
    views = 0

    while True:
        action = ctx.textual.ask_choice(
            "Dig into the log?",
            options=[
                ChoiceOption(value="errors", label="Error in context", variant="primary"),
                ChoiceOption(value="filter", label="Filter entries", variant="default"),
                ChoiceOption(value="workflow", label="One workflow", variant="default"),
                ChoiceOption(value="done", label="Done", variant="default"),
            ],
        )

        if action is None or action == "done":
            break

        if action == "errors":
            views += _explore_errors(ctx, entries)
        elif action == "filter":
            views += _explore_filter(ctx, entries)
        elif action == "workflow":
            views += _explore_workflow(ctx, entries)

    ctx.textual.end_step("success" if views else "skip")
    if not views:
        return Skip("Nothing explored")
    return Success(f"Explored the log ({views} view(s))")


# ── Modes ──────────────────────────────────────────────────────────────────────

def _explore_errors(ctx: WorkflowContext, entries: List[LogEntry]) -> int:
    errors = [e for e in entries if e.level in ERROR_LEVELS]
    if not errors:
        ctx.textual.dim_text("  No error-level entries in this session")
        return 0

    target = _pick_entry(ctx, errors, "Which error do you want to read in context?")
    if target is None:
        return 0

    _show_entry_in_context(ctx, entries, target)
    return 1


def _explore_filter(ctx: WorkflowContext, entries: List[LogEntry]) -> int:
    level_choice = ctx.textual.ask_choice(
        "Which levels?",
        options=[
            ChoiceOption(value="all", label="All", variant="default"),
            ChoiceOption(value="info", label="Info and above", variant="default"),
            ChoiceOption(value="warning", label="Warnings and errors", variant="default"),
            ChoiceOption(value="error", label="Errors only", variant="primary"),
        ],
    )
    if level_choice is None:
        return 0

    levels = {
        "all": None,
        "info": ["info", "warning", *ERROR_LEVELS],
        "warning": ["warning", *ERROR_LEVELS],
        "error": list(ERROR_LEVELS),
    }[level_choice]

    text = ctx.textual.ask_text("Search text (empty = no text filter):", default="")

    needle = text.strip() if text else ""
    matches = filter_entries(entries, levels=levels, text=needle or None)
    if not matches:
        ctx.textual.dim_text("  No entries match that filter")
        return 0

    _show_entry_list(ctx, matches, title=f"{len(matches)} matching entries")

    if len(matches) <= _MAX_PICKABLE and ctx.textual.ask_confirm(
        "Read one of them in context?", default=False
    ):
        target = _pick_entry(ctx, matches, "Which entry?")
        if target is not None:
            _show_entry_in_context(ctx, entries, target)

    return 1


def _explore_workflow(ctx: WorkflowContext, entries: List[LogEntry]) -> int:
    names = workflow_names(entries)
    if not names:
        ctx.textual.dim_text("  No workflow ran in this session")
        return 0

    if len(names) == 1:
        name = names[0]
    else:
        choice = ctx.textual.ask_option(
            "Which workflow?",
            [
                OptionItem(
                    value=index,
                    title=workflow_name,
                    description=(
                        "  "
                        + str(len(filter_entries(entries, workflow=workflow_name)))
                        + " entries"
                    ),
                )
                for index, workflow_name in enumerate(names)
            ],
        )
        if choice is None:
            return 0
        name = names[choice]

    matches = filter_entries(entries, workflow=name)
    _show_entry_list(ctx, matches, title=f"{name} — {len(matches)} entries")
    return 1


# ── Rendering ──────────────────────────────────────────────────────────────────

def _pick_entry(
    ctx: WorkflowContext, candidates: List[LogEntry], question: str
) -> Optional[LogEntry]:
    shown = candidates[:_MAX_PICKABLE]
    if len(candidates) > _MAX_PICKABLE:
        ctx.textual.dim_text(
            f"  Showing the first {_MAX_PICKABLE} of {len(candidates)}"
        )

    options = [
        OptionItem(
            value=index,
            title=f"[{format_time(entry.timestamp)}] {entry.event}",
            description="  " + entry_message(entry)[:140],
        )
        for index, entry in enumerate(shown)
    ]

    choice = ctx.textual.ask_option(question, options)
    return shown[choice] if choice is not None else None


def _show_entry_in_context(
    ctx: WorkflowContext, entries: List[LogEntry], target: LogEntry
) -> None:
    ctx.textual.text("")
    ctx.textual.bold_text(f"{target.event}  —  {format_time(target.timestamp)}")
    ctx.textual.text("")

    payload = format_entry_json(target)
    _mount_text(ctx, payload, max_height=24)

    context = entries_around(entries, target, before=15, after=10)
    ctx.textual.text("")
    ctx.textual.dim_text(
        f"Surrounding entries ({len(context)}, the error marked with ►)"
    )
    lines = [
        ("► " if entry is target else "  ") + format_entry_line(entry)
        for entry in context
    ]
    _mount_text(ctx, "\n".join(lines), max_height=30)
    ctx.textual.text("")


def _show_entry_list(ctx: WorkflowContext, matches: List[LogEntry], title: str) -> None:
    shown = matches[:_MAX_LISTED]
    rows = [
        [
            format_time(entry.timestamp),
            entry.level,
            entry.event[:50],
            entry_message(entry)[:90],
        ]
        for entry in shown
    ]

    ctx.textual.text("")
    ctx.textual.mount(Table(
        headers=["Time", "Level", "Event", "Message"],
        rows=rows,
        title=title,
    ))
    if len(matches) > _MAX_LISTED:
        ctx.textual.dim_text(
            f"  … {len(matches) - _MAX_LISTED} more entries not shown — narrow the filter"
        )
    ctx.textual.text("")


def _mount_text(ctx: WorkflowContext, text: str, *, max_height: int) -> None:
    widget = MultilineInput(text, read_only=True)
    widget.styles.height = min(max_height, max(3, text.count("\n") + 3))
    ctx.textual.mount(widget)
