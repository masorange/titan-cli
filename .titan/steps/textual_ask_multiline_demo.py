from titan_cli.engine.context import WorkflowContext
from titan_cli.engine.results import Error, Success, WorkflowResult


def textual_ask_multiline_demo(ctx: WorkflowContext) -> WorkflowResult:
    """Show ctx.textual.ask_multiline for documentation screenshots."""
    if not ctx.textual:
        return Error("Textual UI context is not available for this step.")

    ctx.textual.begin_step("ask_multiline()")

    try:
        content = ctx.textual.ask_multiline(
            "Enter release notes:",
            default="## Summary\n\n- Document public plugin steps\n- Add Textual API guide",
        )
    except (KeyboardInterrupt, EOFError):
        ctx.textual.end_step("error")
        return Error("User cancelled")

    if not content:
        ctx.textual.end_step("error")
        return Error("Content is required")

    ctx.textual.success_text("Captured multiline content")
    ctx.textual.end_step("success")
    return Success("Rendered ask_multiline() demo")
