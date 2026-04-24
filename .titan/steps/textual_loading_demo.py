import time

from titan_cli.engine.context import WorkflowContext
from titan_cli.engine.results import Error, Success, WorkflowResult


def textual_loading_demo(ctx: WorkflowContext) -> WorkflowResult:
    """Show ctx.textual.loading for documentation screenshots."""
    if not ctx.textual:
        return Error("Textual UI context is not available for this step.")

    ctx.textual.begin_step("loading()")
    with ctx.textual.loading("Validating plugin docs inventory..."):
        time.sleep(6)
    ctx.textual.success_text("Validation completed successfully.")
    ctx.textual.end_step("success")
    return Success("Rendered loading() demo")
