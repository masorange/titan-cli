"""
Step: audit_workflow_run

A focused picture of how one workflow run worked — what it processed, what it
read, how full its budgets were — compared against previous runs of the same
workflow.

Not a failure report: the run may have gone fine. The question here is
whether it did its job well.
"""

from titan_cli.engine import WorkflowContext, WorkflowResult, Success, Error, Skip
from titan_cli.ui.tui.widgets import Table

from operations import (
    build_run_history,
    format_comparison,
    format_duration,
    format_run_header,
    interpret_run,
    label_for,
    profile_workflow_run,
)

# How many identities to list per funnel stage before summarising the rest.
_MAX_ITEMS = 20


def audit_workflow_run(ctx: WorkflowContext) -> WorkflowResult:
    """
    Audit the selected workflow run.

    Inputs:
        workflow_run (WorkflowRun): From select_workflow_run
        workflow_peer_runs (list[WorkflowRun]): The baseline to compare against

    Outputs:
        workflow_run_profile (WorkflowRunProfile)
        workflow_run_interpretation (Interpretation)
        workflow_run_history (RunHistory)
    """
    if not ctx.textual:
        return Error("Textual UI context is not available for this step.")

    ctx.textual.begin_step("Audit Workflow Run")

    run = ctx.get("workflow_run")
    if not run:
        ctx.textual.end_step("error")
        return Error("No run in context. Run select_workflow_run first.")

    if not run.steps:
        ctx.textual.dim_text("That run recorded no steps — nothing to audit")
        ctx.textual.end_step("skip")
        return Skip("Nothing to audit")

    profile = profile_workflow_run(run)
    interpretation = interpret_run(profile)

    history = build_run_history(ctx.get("workflow_peer_runs") or [], run)

    # ── Header ─────────────────────────────────────────────────────────────────
    ctx.textual.text("")
    ctx.textual.bold_text(format_run_header(run))
    if history.runs:
        ctx.textual.dim_text(
            f"Compared against {history.runs} previous run(s) of this workflow "
            "found in the selected logs"
        )
    else:
        ctx.textual.dim_text("No previous run of this workflow in the selected logs")

    # ── What it processed ──────────────────────────────────────────────────────
    if interpretation.stages:
        ctx.textual.text("")
        ctx.textual.bold_text("What the run processed")
        ctx.textual.mount(Table(
            headers=["Stage", "Count", "Named"],
            rows=[
                [
                    stage.label,
                    str(stage.value),
                    "" if not stage.value else ("yes" if stage.items else "—"),
                ]
                for stage in interpretation.stages
            ],
            full_width=False,
        ))

        # The counts above are only actionable once you can see what they are
        # made of, so every stage the log names gets listed out.
        for stage in interpretation.stages:
            if not stage.items:
                continue
            ctx.textual.text("")
            suffix = "" if stage.items_complete else f" (of {stage.value}, partial)"
            ctx.textual.dim_text(f"  {stage.label} — {len(stage.items)}{suffix}:")
            for item in stage.items[:_MAX_ITEMS]:
                ctx.textual.dim_text(f"      {item}")
            if len(stage.items) > _MAX_ITEMS:
                ctx.textual.dim_text(
                    f"      … {len(stage.items) - _MAX_ITEMS} more"
                )
    elif profile.funnel:
        ctx.textual.text("")
        ctx.textual.bold_text("Quantities logged, in order")
        ctx.textual.dim_text(
            "  No interpreter for this workflow — raw field names shown"
        )
        ctx.textual.mount(Table(
            headers=["Step", "Field", "Value"],
            rows=[
                [point.step_id, f"{point.event}.{point.field_name}", str(point.value)]
                for point in profile.funnel[:25]
            ],
        ))

    if interpretation.notes:
        ctx.textual.text("")
        ctx.textual.bold_text("Flagged in this run")
        for note in interpretation.notes:
            ctx.textual.warning_text(f"  {note}")

    # ── Per step ───────────────────────────────────────────────────────────────
    ctx.textual.text("")
    ctx.textual.bold_text("Steps")
    ctx.textual.mount(Table(
        headers=["Step", "Result", "Took", "vs history"],
        rows=[
            [
                step.step_id,
                step.result,
                format_duration(step.duration),
                format_comparison(step, history.compare(step)),
            ]
            for step in run.steps
        ],
        flex_column=3,
    ))

    # ── Detail ─────────────────────────────────────────────────────────────────
    for step_profile in profile.profiled_steps:
        if not (step_profile.tables or step_profile.budgets or step_profile.flags):
            continue

        ctx.textual.text("")
        ctx.textual.bold_text(f"  {step_profile.step.step_id}")

        for budget in step_profile.budgets:
            ctx.textual.dim_text(
                f"    budget {budget.label}: {budget.actual:,.0f} / "
                f"{budget.limit:,.0f} = {budget.used_pct:.0f}%"
            )
        for flag in step_profile.flags[:8]:
            ctx.textual.dim_text(f"    flag: {flag}")

        for table in step_profile.tables:
            # Printed as text, not passed as the Table's title: that renders
            # into `border_title`, which is invisible on a borderless table —
            # so every table came out unlabelled.
            title = label_for(run.name, table.event) or table.event
            ctx.textual.dim_text(f"    {title}  ({table.occurrences})")
            ctx.textual.mount(Table(headers=table.columns, rows=table.rows))

        # Repeated calls that carry nothing to tell apart, as one line each.
        for name, value in step_profile.metrics:
            if value.endswith(("calls", "messages")) or " calls " in value or " messages " in value:
                ctx.textual.dim_text(f"    {name}: {value}")

    ctx.textual.text("")
    ctx.textual.end_step("success")
    return Success(
        f"Audited {run.name}",
        metadata={
            "workflow_run_profile": profile,
            "workflow_run_interpretation": interpretation,
            "workflow_run_history": history,
        },
    )
