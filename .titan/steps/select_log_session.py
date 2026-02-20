"""
Step: select_log_session

Parse the log file and let the user pick a session to analyze.
"""

from pathlib import Path
from titan_cli.engine import WorkflowContext, WorkflowResult, Success, Error
from titan_cli.ui.tui.widgets import OptionItem

from operations import parse_log_file, format_session_label


def select_log_session(ctx: WorkflowContext) -> WorkflowResult:
    """
    Parse the log file and present a session selector.

    Inputs (from ctx.data):
        log_path (str): Path to the log file

    Outputs (saved to ctx.data):
        log_session: Selected LogSession object
    """
    if not ctx.textual:
        return Error("Textual UI context is not available for this step.")

    ctx.textual.begin_step("Select Session")

    log_path = ctx.get("log_path")
    if not log_path:
        ctx.textual.end_step("error")
        return Error("No log path in context. Run prompt_log_path first.")

    ctx.textual.text("")
    ctx.textual.dim_text(f"Parsing {log_path}...")

    try:
        sessions = parse_log_file(Path(log_path))
    except Exception as e:
        ctx.textual.error_text(f"Failed to parse log file: {e}")
        ctx.textual.end_step("error")
        return Error(f"Failed to parse log file: {e}")

    if not sessions:
        ctx.textual.error_text("No sessions found in log file")
        ctx.textual.end_step("error")
        return Error("No sessions found in log file")

    ctx.textual.dim_text(f"Found {len(sessions)} session(s)")

    if len(sessions) == 1:
        selected = sessions[0]
        ctx.textual.text("")
        ctx.textual.success_text("✓ Single session found, selecting it automatically")
    else:
        # Show latest sessions first
        sessions_desc = list(reversed(sessions))

        options = [
            OptionItem(
                value=i,
                title=format_session_label(s),
                description=_session_description(s),
            )
            for i, s in enumerate(sessions_desc)
        ]

        ctx.textual.text("")
        selected_idx = ctx.textual.ask_option("Select a session to analyze:", options)

        if selected_idx is None:
            ctx.textual.end_step("error")
            return Error("No session selected")

        selected = sessions_desc[selected_idx]

    ctx.set("log_session", selected)

    ctx.textual.end_step("success")
    return Success(f"Session selected: {format_session_label(selected)}")


def _session_description(session) -> str:
    from operations import analyze_session
    analysis = analyze_session(session)
    wf_count = len(analysis.workflows)
    err_count = len(analysis.errors)
    parts = []
    if wf_count:
        parts.append(f"{wf_count} workflow{'s' if wf_count != 1 else ''}")
    if err_count:
        parts.append(f"{err_count} error{'s' if err_count != 1 else ''}")
    return "  " + "  ·  ".join(parts) if parts else "  No workflows"
