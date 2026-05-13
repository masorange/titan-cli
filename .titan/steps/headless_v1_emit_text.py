"""Emit a simple text output for the headless V1 demo workflow."""

from titan_cli.engine import Success, WorkflowContext, WorkflowResult, Error


def headless_v1_emit_text(ctx: WorkflowContext) -> WorkflowResult:
    """Emit the first text output used by the headless V1 demo workflow."""
    if not ctx.textual:
        return Error("Textual UI context is not available for this step.")

    ctx.textual.begin_step("Headless Demo Text")
    ctx.textual.text("demo text output")
    ctx.textual.end_step("success")
    return Success("Demo text emitted")
