from titan_cli.engine.context import WorkflowContext
from titan_cli.engine.results import Error, Success, WorkflowResult


def textual_text_methods_demo(ctx: WorkflowContext) -> WorkflowResult:
    """Show the core ctx.textual text methods together for documentation screenshots."""
    if not ctx.textual:
        return Error("Textual UI context is not available for this step.")

    ctx.textual.begin_step("Text Methods")
    ctx.textual.text("Normal message")
    ctx.textual.bold_text("Important message")
    ctx.textual.dim_text("Secondary information")
    ctx.textual.primary_text("Primary color message")
    ctx.textual.bold_primary_text("Bold primary message")
    ctx.textual.success_text("Operation successful")
    ctx.textual.warning_text("Warning message")
    ctx.textual.error_text("Operation failed")
    ctx.textual.end_step("success")
    return Success("Rendered text methods demo")
