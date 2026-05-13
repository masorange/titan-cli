"""Request a confirmation prompt for the headless V1 demo workflow."""

from titan_cli.engine import Error, Success, WorkflowContext, WorkflowResult


def headless_v1_confirm_continue(ctx: WorkflowContext) -> WorkflowResult:
    """Ask whether the headless V1 demo workflow should continue."""
    if not ctx.textual:
        return Error("Textual UI context is not available for this step.")

    ctx.textual.begin_step("Headless Demo Confirm")
    should_continue = ctx.textual.ask_confirm("Continue headless demo?", default=True)
    if not should_continue:
        ctx.textual.error_text("Headless demo declined by user")
        ctx.textual.end_step("error")
        return Error("Headless demo declined by user")

    ctx.textual.success_text("Headless demo confirmed")
    ctx.textual.end_step("success")
    return Success("Headless demo confirmed")
