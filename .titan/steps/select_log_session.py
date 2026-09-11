"""
Step: select_log_session

Index the selected log files and let the user pick a session.
"""

from pathlib import Path

from titan_cli.engine import WorkflowContext, WorkflowResult, Success, Error
from titan_cli.ui.tui.widgets import OptionItem

from operations import (
    format_session_description,
    format_session_label,
    index_sessions,
)


def select_log_session(ctx: WorkflowContext) -> WorkflowResult:
    """
    Index the log files and present a session selector.

    The index is a byte scan: it records where each session lives and counts
    its entries without parsing them. Only the chosen session is parsed, by
    the next step.

    Inputs:
        log_paths (list[str]): Log file paths, oldest first

    Outputs:
        log_session_ref (SessionRef): The selected session's location and counts
    """
    if not ctx.textual:
        return Error("Textual UI context is not available for this step.")

    ctx.textual.begin_step("Select Session")

    raw_paths = ctx.get("log_paths") or []
    paths = [Path(path) for path in raw_paths]
    if not paths:
        ctx.textual.end_step("error")
        return Error("No log paths in context. Run select_log_source first.")

    with ctx.textual.loading(f"Indexing {len(paths)} log file(s)…"):
        try:
            sessions = index_sessions(paths)
        except OSError as error:
            ctx.textual.error_text(f"Failed to read log files: {error}")
            ctx.textual.end_step("error")
            return Error(f"Failed to read log files: {error}")

    if not sessions:
        ctx.textual.error_text("No sessions found in the selected log files")
        ctx.textual.end_step("error")
        return Error("No sessions found")

    ctx.textual.dim_text(f"Found {len(sessions)} session(s)")

    if len(sessions) == 1:
        selected = sessions[0]
        ctx.textual.success_text("✓ Single session found, selecting it automatically")
    else:
        newest_first = list(reversed(sessions))
        options = [
            OptionItem(
                value=index,
                title=format_session_label(session),
                description=format_session_description(session),
            )
            for index, session in enumerate(newest_first)
        ]

        choice = ctx.textual.ask_option("Select a session to analyze:", options)
        if choice is None:
            ctx.textual.end_step("error")
            return Error("No session selected")

        selected = newest_first[choice]

    if selected.spans_rotation:
        ctx.textual.warning_text(
            "  This session was split by log rotation across "
            + " + ".join(path.name for path in selected.files)
        )
    if selected.truncated_head:
        ctx.textual.warning_text(
            "  The start of this session is gone — rotation deleted the file "
            "that held it"
        )

    ctx.textual.end_step("success")
    return Success(
        f"Session selected: {format_session_label(selected)}",
        metadata={"log_session_ref": selected},
    )
