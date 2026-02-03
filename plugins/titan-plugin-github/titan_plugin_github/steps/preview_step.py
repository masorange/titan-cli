from titan_cli.engine.context import WorkflowContext
from titan_cli.engine.results import WorkflowResult, Success, Error

def preview_and_confirm_issue_step(ctx: WorkflowContext) -> WorkflowResult:
    """
    Show a preview of the AI-generated issue and ask for confirmation.
    """
    if not ctx.textual:
        return Error("Textual UI context is not available for this step.")

    # Begin step container
    ctx.textual.begin_step("Preview and Confirm Issue")

    issue_title = ctx.get("issue_title")
    issue_body = ctx.get("issue_body")

    if not issue_title or not issue_body:
        ctx.textual.error_text("issue_title or issue_body not found in context")
        ctx.textual.end_step("error")
        return Error("issue_title or issue_body not found in context")

    # Show preview header
    ctx.textual.text("")  # spacing
    ctx.textual.bold_text("AI-Generated Issue Preview")
    ctx.textual.text("")  # spacing

    # Show title
    ctx.textual.bold_text("Title:")
    ctx.textual.primary_text(f"  {issue_title}")
    ctx.textual.text("")  # spacing

    # Show description
    ctx.textual.bold_text("Description:")
    # Render markdown in a scrollable container
    ctx.textual.markdown(issue_body)

    ctx.textual.text("")  # spacing

    try:
        if not ctx.textual.ask_confirm("Use this AI-generated issue?", default=True):
            ctx.textual.warning_text("User rejected AI-generated issue")
            ctx.textual.end_step("error")
            return Error("User rejected AI-generated issue")
    except (KeyboardInterrupt, EOFError):
        ctx.textual.error_text("User cancelled operation")
        ctx.textual.end_step("error")
        return Error("User cancelled operation")

    ctx.textual.success_text("User confirmed AI-generated issue")
    ctx.textual.end_step("success")
    return Success("User confirmed AI-generated issue")
