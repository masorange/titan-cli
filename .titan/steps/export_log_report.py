"""
Step: export_log_report

Hand the session report out of the TUI: to the clipboard, to a file, or as
selectable text — so it can be pasted into another assistant, an issue, or a
message.

The report carries the evidence and not just the diagnosis. Another model
asked "why did this fail?" needs the timeline and the error payloads; the
conclusion alone gives it nothing to reason from. It is therefore offered
whether or not the AI step produced anything.
"""

from pathlib import Path
from typing import Optional

from titan_cli.engine import WorkflowContext, WorkflowResult, Success, Error, Skip
from titan_cli.ui.tui.widgets import ChoiceOption, MultilineInput

from operations import (
    DEFAULT_REPORT_DIR,
    build_report_document,
    default_report_path,
)


def export_log_report(ctx: WorkflowContext) -> WorkflowResult:
    """
    Export the session report (diagnosis + evidence).

    Inputs:
        log_analysis (SessionAnalysis): From analyze_log_session
        log_diagnosis (str): From ai_diagnose_log_session, when it ran

    Outputs:
        log_report (str): The report Markdown
        log_report_path (str): Where it was written, when it was saved
    """
    if not ctx.textual:
        return Error("Textual UI context is not available for this step.")

    ctx.textual.begin_step("Export Report")

    analysis = ctx.get("log_analysis")
    if not analysis:
        ctx.textual.end_step("error")
        return Error("No analysis in context. Run analyze_log_session first.")

    diagnosis = ctx.get("log_diagnosis")
    report = build_report_document(analysis, diagnosis)

    ctx.textual.dim_text(
        f"Report ready — {len(report):,} characters"
        + ("  (diagnosis + evidence)" if diagnosis else "  (evidence only)")
    )

    action = ctx.textual.ask_choice(
        "Take the report with you?",
        options=[
            ChoiceOption(value="both", label="Copy and save", variant="primary"),
            ChoiceOption(value="copy", label="Copy to clipboard", variant="default"),
            ChoiceOption(value="save", label="Save to file", variant="default"),
            ChoiceOption(value="show", label="Show as text", variant="default"),
            ChoiceOption(value="skip", label="No thanks", variant="default"),
        ],
    )

    if action is None or action == "skip":
        ctx.textual.end_step("skip")
        return Skip("Report not exported")

    metadata = {"log_report": report}
    copied = False
    path: Optional[Path] = None

    if action in ("copy", "both"):
        copied = _copy_to_clipboard(ctx, report)
        if copied:
            # The terminal is asked, not told: OSC 52 can be dropped without
            # any error reaching us, so this claims only what we know.
            ctx.textual.success_text("✓ Sent to the clipboard (OSC 52)")
            if action == "copy":
                ctx.textual.dim_text(
                    "  If nothing pastes, your terminal blocks OSC 52 — "
                    "re-run and choose Save to file."
                )
        else:
            ctx.textual.warning_text(
                "Could not reach the clipboard — this terminal may not support "
                "OSC 52. Saving the report instead."
            )

    if action in ("save", "both") or (action == "copy" and not copied):
        path = _save(ctx, analysis.session, report)
        if path is None:
            ctx.textual.end_step("error")
            return Error("Failed to write the report")
        ctx.textual.success_text(f"✓ Saved to {path}")
        ctx.textual.dim_text(f"  cat {path}")
        metadata["log_report_path"] = str(path)

    if action == "show":
        _show(ctx, report)

    ctx.textual.end_step("success")
    return Success("Report exported", metadata=metadata)


def _copy_to_clipboard(ctx: WorkflowContext, text: str) -> bool:
    """
    Put text on the system clipboard through the terminal (OSC 52).

    Steps run on a worker thread, so the call has to be handed back to the
    Textual event loop. Terminals that refuse OSC 52 fail silently, which is
    why every caller has a file fallback.
    """
    app = getattr(ctx.textual, "app", None)
    if app is None:
        return False
    try:
        app.call_from_thread(app.copy_to_clipboard, text)
        return True
    except Exception:
        return False


def _save(ctx: WorkflowContext, session, report: str) -> Optional[Path]:
    path = default_report_path(session)
    try:
        DEFAULT_REPORT_DIR.mkdir(parents=True, exist_ok=True)
        path.write_text(report, encoding="utf-8")
    except OSError as error:
        ctx.textual.error_text(f"Could not write {path}: {error}")
        return None
    return path


def _show(ctx: WorkflowContext, report: str) -> None:
    ctx.textual.text("")
    ctx.textual.dim_text("Select with the mouse to copy:")
    widget = MultilineInput(report, read_only=True)
    widget.styles.height = 30
    ctx.textual.mount(widget)
    ctx.textual.text("")
