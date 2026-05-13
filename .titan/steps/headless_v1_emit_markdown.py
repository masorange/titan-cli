"""Emit a markdown output for the headless V1 demo workflow."""

from titan_cli.engine import Error, Success, WorkflowContext, WorkflowResult


def headless_v1_emit_markdown(ctx: WorkflowContext) -> WorkflowResult:
    """Emit the final markdown output used by the headless V1 demo workflow."""
    if not ctx.textual:
        return Error("Textual UI context is not available for this step.")

    ctx.textual.begin_step("Headless Demo Markdown")
    ctx.textual.markdown("# Demo complete")
    ctx.textual.end_step("success")
    return Success("Demo markdown emitted")
