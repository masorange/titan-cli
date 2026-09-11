"""
Step: select_workflow

Pick a workflow from those that actually appear in the selected logs.

The entry point is the workflow, not the session: you know which workflow you
want to look at, and you have no way of knowing which of a hundred sessions
happened to run it.
"""

from pathlib import Path

from titan_cli.engine import WorkflowContext, WorkflowResult, Success, Error
from titan_cli.ui.tui.widgets import OptionItem

from operations import (
    format_time,
    inventory_runs,
    summarize_workflows,
)


def select_workflow(ctx: WorkflowContext) -> WorkflowResult:
    """
    List the workflows found in the logs and let the user pick one.

    Inputs:
        log_paths (list[str]): Log file paths, oldest first

    Outputs:
        workflow_name (str): The chosen workflow
        workflow_run_refs (list[RunRef]): Every run found, of every workflow
    """
    if not ctx.textual:
        return Error("Textual UI context is not available for this step.")

    ctx.textual.begin_step("Select Workflow")

    raw_paths = ctx.get("log_paths") or []
    paths = [Path(path) for path in raw_paths]
    if not paths:
        ctx.textual.end_step("error")
        return Error("No log paths in context. Run select_log_source first.")

    with ctx.textual.loading("Looking for workflow runs in the logs…"):
        refs = inventory_runs(paths)

    if not refs:
        ctx.textual.error_text("No workflow run found in the selected logs")
        ctx.textual.end_step("error")
        return Error("No workflow runs found")

    summaries = summarize_workflows(refs)
    ctx.textual.dim_text(
        f"Found {len(refs)} run(s) of {len(summaries)} workflow(s)"
    )

    options = [
        OptionItem(
            value=index,
            title=summary.name,
            description=_describe(summary),
        )
        for index, summary in enumerate(summaries)
    ]

    choice = ctx.textual.ask_option("Which workflow do you want to look at?", options)
    if choice is None:
        ctx.textual.end_step("error")
        return Error("No workflow selected")

    chosen = summaries[choice]
    ctx.textual.success_text(f"✓ {chosen.name}  ({chosen.runs} run(s))")
    ctx.textual.end_step("success")
    return Success(
        f"Workflow selected: {chosen.name}",
        metadata={"workflow_name": chosen.name, "workflow_run_refs": refs},
    )


def _describe(summary) -> str:
    parts = [f"{summary.runs} run{'s' if summary.runs != 1 else ''}"]
    if summary.failed:
        parts.append(f"✖ {summary.failed} with a failure")
    if summary.last_seen:
        parts.append(f"last {format_time(summary.last_seen, '%d %b %H:%M')}")
    parts.append(f"{summary.total_steps} steps total")
    return "  ·  " + "  ·  ".join(parts)
