"""
Step: analyze_log_session

Display a structured analysis of the selected log session:
  - Timeline of workflow runs and their steps
  - Errors and warnings
  - Slow operations
"""

from textual.app import ComposeResult

from titan_cli.engine import WorkflowContext, WorkflowResult, Success, Error
from titan_cli.ui.tui.widgets import Table, PanelContainer, ErrorText, DimText

from operations import (
    WorkflowRun,
    analyze_session,
    SLOW_THRESHOLD_SECONDS,
    STEP_RESULT_ICONS,
    WORKFLOW_STATUS_ICONS,
)


class _WorkflowPanel(PanelContainer):
    """Local widget — not exported. Displays a single workflow run in a panel."""

    _STATUS_VARIANT = {
        "success": "success",
        "failed": "error",
        "exited": "warning",
    }

    def __init__(self, wf: WorkflowRun, **kwargs):
        dur_str = f"  {wf.duration:.1f}s" if wf.duration is not None else ""
        icon = WORKFLOW_STATUS_ICONS.get(wf.status, "❓")
        title = f"{icon} {wf.name}{dur_str}"
        variant = self._STATUS_VARIANT.get(wf.status, "default")
        super().__init__(variant=variant, title=title, **kwargs)
        self._wf = wf

    def compose(self) -> ComposeResult:
        wf = self._wf
        if wf.failed_at:
            yield ErrorText(f"Failed at step: {wf.failed_at}")
        if wf.steps:
            rows = []
            for step in wf.steps:
                icon = STEP_RESULT_ICONS.get(step.result, "❓")
                dur = f"{step.duration:.2f}s" if step.duration is not None else "—"
                detail = (step.error or step.message or "")[:80]
                rows.append([icon, step.step_id, dur, detail])
            yield Table(headers=["", "Step", "Duration", "Info"], rows=rows)
        else:
            yield DimText("No steps recorded")


def analyze_log_session(ctx: WorkflowContext) -> WorkflowResult:
    """
    Analyze and display a selected log session.

    Inputs (from ctx.data):
        log_session: LogSession object from select_log_session
    """
    if not ctx.textual:
        return Error("Textual UI context is not available for this step.")

    ctx.textual.begin_step("Session Analysis")

    session = ctx.get("log_session")
    if not session:
        ctx.textual.end_step("error")
        return Error("No session in context. Run select_log_session first.")

    analysis = analyze_session(session)

    # ── Header ─────────────────────────────────────────────────────────────────
    ctx.textual.text("")
    if session.start_time:
        ctx.textual.dim_text(f"Session start : {session.start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    if session.end_time:
        ctx.textual.dim_text(f"Session end   : {session.end_time.strftime('%H:%M:%S')}")
    if session.duration_seconds is not None:
        ctx.textual.dim_text(f"Duration      : {session.duration_seconds:.0f}s")
    if session.pid:
        ctx.textual.dim_text(f"PID           : {session.pid}")
    if session.version:
        ctx.textual.dim_text(f"Version       : {session.version}")
    if session.mode:
        ctx.textual.dim_text(f"Mode          : {session.mode}")
    ctx.textual.dim_text(f"Log events    : {len(session.entries)}")

    # ── Workflow timeline ───────────────────────────────────────────────────────
    if analysis.workflows:
        ctx.textual.text("")
        ctx.textual.bold_text(f"Workflows ({len(analysis.workflows)})")
        for wf in analysis.workflows:
            ctx.textual.mount(_WorkflowPanel(wf))
    else:
        ctx.textual.text("")
        ctx.textual.dim_text("No workflows recorded in this session")

    # ── Errors ─────────────────────────────────────────────────────────────────
    if analysis.errors:
        ctx.textual.text("")
        ctx.textual.bold_text(f"Errors ({len(analysis.errors)})")
        ctx.textual.text("")

        rows = []
        for err in analysis.errors:
            ts = err.timestamp.strftime("%H:%M:%S") if err.timestamp else "?"
            msg = (
                err.raw.get("error")
                or err.raw.get("message")
                or err.raw.get("reason")
                or err.event
            )
            rows.append([ts, err.event, str(msg)[:120]])

        ctx.textual.mount(Table(
            headers=["Time", "Event", "Message"],
            rows=rows,
            title="Errors & Exceptions",
        ))

    # ── Warnings ───────────────────────────────────────────────────────────────
    if analysis.warnings:
        ctx.textual.text("")
        ctx.textual.bold_text(f"Warnings ({len(analysis.warnings)})")
        ctx.textual.text("")
        for warn in analysis.warnings:
            ts = warn.timestamp.strftime("%H:%M:%S") if warn.timestamp else "?"
            msg = warn.raw.get("message") or warn.raw.get("reason") or warn.event
            ctx.textual.warning_text(f"  [{ts}] {warn.event}: {msg[:120]}")

    # ── Slow operations ─────────────────────────────────────────────────────────
    if analysis.slow_ops:
        ctx.textual.text("")
        ctx.textual.bold_text(f"Slow Operations  (>{SLOW_THRESHOLD_SECONDS}s)")
        ctx.textual.text("")

        sorted_slow = sorted(
            analysis.slow_ops,
            key=lambda e: e.raw.get("duration", 0),
            reverse=True,
        )[:10]

        rows = []
        for op in sorted_slow:
            dur = op.raw.get("duration", 0)
            wf = op.raw.get("workflow") or op.raw.get("step_id") or ""
            rows.append([f"{dur:.2f}s", op.event, wf])

        ctx.textual.mount(Table(
            headers=["Duration", "Event", "Context"],
            rows=rows,
            title="Slowest Operations",
            full_width=False,
        ))

    # ── Summary ────────────────────────────────────────────────────────────────
    ctx.textual.text("")
    ctx.textual.success_text("✅  Analysis complete")

    error_count = len(analysis.errors)
    warning_count = len(analysis.warnings)
    if error_count == 0 and warning_count == 0:
        ctx.textual.dim_text("  No errors or warnings found")
    else:
        if error_count:
            ctx.textual.dim_text(f"  {error_count} error(s) found")
        if warning_count:
            ctx.textual.dim_text(f"  {warning_count} warning(s) found")

    ctx.textual.text("")
    ctx.textual.end_step("success")
    return Success(
        f"Session analyzed: {len(analysis.workflows)} workflow(s), "
        f"{error_count} error(s)"
    )
