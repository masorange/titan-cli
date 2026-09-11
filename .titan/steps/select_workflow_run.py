"""
Step: select_workflow_run

Pick which run of the chosen workflow to inspect, with enough detail on each
to tell them apart — when it ran, how it ended, how many steps, where it
broke.
"""

from titan_cli.engine import WorkflowContext, WorkflowResult, Success, Error
from titan_cli.ui.tui.widgets import OptionItem

from operations import (
    WORKFLOW_STATUS_ICONS,
    format_run_choice,
    format_time,
    load_run,
)


def select_workflow_run(ctx: WorkflowContext) -> WorkflowResult:
    """
    Choose one run of the selected workflow and read it back in full.

    Inputs:
        workflow_name (str): From select_workflow
        workflow_run_refs (list[RunRef]): From select_workflow

    Outputs:
        workflow_run: The chosen run, with every step's entries attached
        workflow_peer_runs: The other runs of this workflow, for comparison
    """
    if not ctx.textual:
        return Error("Textual UI context is not available for this step.")

    ctx.textual.begin_step("Select Run")

    name = ctx.get("workflow_name")
    refs = ctx.get("workflow_run_refs") or []
    if not name or not refs:
        ctx.textual.end_step("error")
        return Error("No workflow in context. Run select_workflow first.")

    mine = [ref for ref in refs if ref.name == name]
    if not mine:
        ctx.textual.error_text(f"No run of '{name}' left in the logs")
        ctx.textual.end_step("error")
        return Error(f"No run of '{name}' found")

    newest_first = list(reversed(mine))

    if len(newest_first) == 1:
        chosen = newest_first[0]
        ctx.textual.dim_text("Only one run of this workflow — selecting it")
    else:
        options = [
            OptionItem(
                value=index,
                title=(
                    f"{WORKFLOW_STATUS_ICONS.get(ref.run.status, '❓')}  "
                    f"{format_time(ref.run.started_at, '%d %b  %H:%M:%S')}"
                ),
                description=format_run_choice(ref),
            )
            for index, ref in enumerate(newest_first)
        ]
        choice = ctx.textual.ask_option(f"Which run of '{name}'?", options)
        if choice is None:
            ctx.textual.end_step("error")
            return Error("No run selected")
        chosen = newest_first[choice]

    with ctx.textual.loading("Reading that run…"):
        run = load_run(chosen)

    if run is None:
        ctx.textual.error_text("That run could not be read back from the log")
        ctx.textual.end_step("error")
        return Error("Run could not be re-read")

    ctx.textual.success_text(
        f"✓ {name} — {format_time(run.started_at, '%d %b %H:%M:%S')}"
    )
    ctx.textual.end_step("success")
    return Success(
        f"Run selected: {name}",
        metadata={
            "workflow_run": run,
            # Every other run of this workflow, entries stripped: the
            # historical baseline, already in memory and free.
            "workflow_peer_runs": [
                ref.run for ref in mine if ref is not chosen
            ],
        },
    )
