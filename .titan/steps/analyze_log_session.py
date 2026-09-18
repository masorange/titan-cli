"""
Step: analyze_log_session

Parse the selected session and display a structured analysis:
  - Timeline of workflow runs and their steps
  - Errors and warnings, with repeats collapsed
  - Slow operations
"""

from textual.app import ComposeResult

from titan_cli.engine import WorkflowContext, WorkflowResult, Success, Error
from titan_cli.ui.tui.widgets import Table, PanelContainer, DimText, MultilineInput

from operations import (
    SLOW_THRESHOLD_SECONDS,
    STEP_RESULT_ICONS,
    STEP_RESULT_LEGEND,
    WORKFLOW_STATUS_ICONS,
    WorkflowRun,
    analyze_session,
    format_duration,
    format_time,
    load_session,
)


class _WorkflowPanel(PanelContainer):
    """Local widget — not exported. Displays a single workflow run in a panel."""

    _STATUS_VARIANT = {
        "success": "success",
        "failed": "error",
        "exited": "warning",
        "aborted": "warning",
        "incomplete": "warning",
    }

    def __init__(self, wf: WorkflowRun, **kwargs):
        icon = WORKFLOW_STATUS_ICONS.get(wf.status, "❓")
        variant = self._STATUS_VARIANT.get(wf.status, "default")
        super().__init__(variant=variant, title=f"{icon}  {wf.name}", **kwargs)
        self._wf = wf

    def compose(self) -> ComposeResult:
        wf = self._wf

        # The outcome in words, above the steps. A bare timestamp next to the
        # name reads as a duration, and a warning icon alone does not say
        # whether the run failed or merely never logged an ending.
        facts = [wf.status_label]
        if wf.started_at:
            facts.append(f"started {format_time(wf.started_at)}")
        if wf.duration is not None:
            facts.append(f"took {format_duration(wf.duration)}")
        facts.append(wf.step_summary)
        yield DimText("   ·   ".join(facts))

        if wf.steps:
            rows = []
            for step in wf.steps:
                icon = STEP_RESULT_ICONS.get(step.result, "❓")
                detail = (step.error or step.message or "")[:100]
                rows.append([
                    format_time(step.timestamp),
                    icon,
                    step.step_id,
                    format_duration(step.duration),
                    detail,
                ])
            yield Table(
                headers=["Time", "", "Step", "Took", "Info"],
                rows=rows,
                flex_column=4,
            )
        else:
            yield DimText("No steps recorded")

        failed = [s for s in wf.steps if s.result in ("failed", "exception") and s.error]
        if failed:
            error_text = "\n".join(f"{s.step_id}: {s.error}" for s in failed)
            widget = MultilineInput(error_text, read_only=True)
            widget.styles.height = max(3, error_text.count("\n") + 3)
            yield widget


def _headline(analysis, warning_total: int) -> str:
    """One line answering 'did this session go well?' before any detail."""
    runs = analysis.workflows
    failed = [run for run in runs if run.status == "failed"]
    unfinished = [run for run in runs if run.status in ("incomplete", "aborted", "exited")]

    if not runs:
        verdict = "No workflow ran"
    elif failed:
        verdict = f"{len(failed)} of {len(runs)} workflow(s) failed"
    elif unfinished:
        verdict = f"{len(runs)} workflow(s), {len(unfinished)} without a recorded ending"
    else:
        verdict = f"All {len(runs)} workflow(s) completed"

    tail = []
    if analysis.error_entry_count:
        tail.append(f"{analysis.error_entry_count} error entries")
    if warning_total:
        tail.append(f"{warning_total} warnings")
    return verdict + ("   —   " + ", ".join(tail) if tail else "   —   no errors or warnings")


def analyze_log_session(ctx: WorkflowContext) -> WorkflowResult:
    """
    Parse and display the selected log session.

    Inputs:
        log_session_ref (SessionRef): From select_log_session

    Outputs:
        log_session (LogSession): The parsed session, for the later steps
        log_analysis (SessionAnalysis): Its analysis
    """
    if not ctx.textual:
        return Error("Textual UI context is not available for this step.")

    ctx.textual.begin_step("Session Analysis")

    ref = ctx.get("log_session_ref")
    if not ref:
        ctx.textual.end_step("error")
        return Error("No session in context. Run select_log_session first.")

    with ctx.textual.loading("Parsing session…"):
        session = load_session(ref)
        analysis = analyze_session(session)

    if not session.entries:
        ctx.textual.error_text("The session holds no readable log entries")
        ctx.textual.end_step("error")
        return Error("Session has no readable entries")

    # ── Header ─────────────────────────────────────────────────────────────────
    # The headline first: what this session did and whether it went wrong.
    # The identifying details follow on one line, because nobody reads six
    # aligned rows to find out it was PID 909890.
    warning_total = sum(group.count for group in analysis.warnings)
    ctx.textual.text("")
    ctx.textual.bold_text(_headline(analysis, warning_total))
    ctx.textual.dim_text(
        f"{format_time(session.start_time, '%a %d %b %Y, %H:%M:%S')} → "
        f"{format_time(session.end_time)} local   ·   "
        f"{format_duration(session.duration_seconds)}   ·   "
        f"{len(session.entries):,} log events"
    )
    ctx.textual.dim_text(
        "   ·   ".join(filter(None, [
            f"titan {session.version}" if session.version else "",
            session.mode,
            f"PID {session.pid}" if session.pid else "",
            ", ".join(path.name for path in ref.files),
        ]))
    )

    # ── Workflow timeline ──────────────────────────────────────────────────────
    ctx.textual.text("")
    if analysis.workflows:
        ctx.textual.bold_text(f"Workflows ({len(analysis.workflows)})")
        ctx.textual.dim_text(STEP_RESULT_LEGEND)
        for run in analysis.workflows:
            ctx.textual.mount(_WorkflowPanel(run))
    else:
        ctx.textual.dim_text("No workflows recorded in this session")

    # ── Errors ─────────────────────────────────────────────────────────────────
    # The count is stated once, split between what the timeline above already
    # showed and what it did not, so the two sections cannot contradict.
    if analysis.error_entry_count:
        ctx.textual.text("")
        ctx.textual.bold_text(f"Errors ({analysis.error_entry_count} entries)")
        if analysis.timeline_error_count:
            ctx.textual.dim_text(
                f"  {analysis.timeline_error_count} of them are the step and workflow "
                "failures shown above"
            )
        ctx.textual.text("")

    # Only the errors that can actually be to blame get a table. The ones
    # logged inside steps that went on to succeed — a test suite inside the
    # workflow logs hundreds of deliberate failures — are one counted line.
    noisy = analysis.looks_like_test_noise
    blameable = analysis.implicated_errors + (
        [] if noisy else analysis.unattributed_errors
    )
    if blameable:
        rows = []
        for group in blameable:
            repeat = f"x{group.count}" if group.count > 1 else ""
            rows.append([
                format_time(group.entry.timestamp),
                repeat,
                group.entry.event,
                group.message[:120],
            ])
        ctx.textual.mount(Table(
            headers=["Time", "", "Event", "Message"],
            rows=rows,
            title="Errors that could explain a failure",
        ))
    elif analysis.error_entry_count:
        ctx.textual.dim_text("  None of them can explain a failure")

    if noisy:
        ctx.textual.dim_text(
            f"  + {len(analysis.unattributed_errors)} distinct *_failed events "
            "logged in seconds with no workflow running — the test suite writing "
            "to this same log, not session failures"
        )
    if analysis.incidental_errors:
        ctx.textual.dim_text(
            f"  + {analysis.incidental_error_count} error entries "
            f"({len(analysis.incidental_errors)} distinct) logged inside steps that "
            "succeeded — not session failures"
        )

    if analysis.quota_exhausted_providers:
        ctx.textual.text("")
        ctx.textual.warning_text(
            "  Provider quota exhausted: "
            + ", ".join(analysis.quota_exhausted_providers)
        )

    # ── Warnings ───────────────────────────────────────────────────────────────
    if analysis.warnings:
        total = sum(group.count for group in analysis.warnings)
        ctx.textual.text("")
        ctx.textual.bold_text(
            f"Warnings ({total} entries, {len(analysis.warnings)} distinct)"
        )
        ctx.textual.text("")
        for group in analysis.warnings[:15]:
            repeat = f" (x{group.count})" if group.count > 1 else ""
            ctx.textual.warning_text(
                f"  [{format_time(group.entry.timestamp)}] "
                f"{group.entry.event}{repeat}: {group.message[:120]}"
            )
        if len(analysis.warnings) > 15:
            ctx.textual.dim_text(f"  … {len(analysis.warnings) - 15} more distinct warnings")

    if analysis.warnings_outside_steps:
        ctx.textual.dim_text(
            f"  + {analysis.warnings_outside_steps} warnings logged outside any step "
            "(same source as the ignorable errors)"
        )

    # ── Slow operations ────────────────────────────────────────────────────────
    if analysis.slow_ops:
        ctx.textual.text("")
        ctx.textual.bold_text(f"Slow Operations  (>{SLOW_THRESHOLD_SECONDS}s)")
        ctx.textual.dim_text("  Workflow and step timings are in the timeline above")
        ctx.textual.text("")

        rows = []
        for entry in analysis.slow_ops[:10]:
            context = entry.raw.get("workflow") or entry.raw.get("step_id") or ""
            rows.append([
                format_duration(entry.raw.get("duration")),
                entry.event,
                str(context),
            ])

        ctx.textual.mount(Table(
            headers=["Duration", "Event", "Context"],
            rows=rows,
            title="Slowest Operations",
            full_width=False,
        ))

    # ── Summary ────────────────────────────────────────────────────────────────
    # No recap of the counts here: they are the headline at the top. What is
    # worth saying at the bottom is what can be done next.
    ctx.textual.text("")
    ctx.textual.success_text("✅  Analysis complete")
    ctx.textual.dim_text(
        "  Next: an AI diagnosis, an exportable report, and the raw entries "
        "around any error"
    )
    ctx.textual.text("")
    ctx.textual.end_step("success")
    return Success(
        f"Session analyzed: {len(analysis.workflows)} workflow(s), "
        f"{analysis.error_entry_count} error entry/entries",
        metadata={"log_session": session, "log_analysis": analysis},
    )
