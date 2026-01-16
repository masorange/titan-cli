from titan_cli.engine.context import WorkflowContext
from titan_cli.engine.results import WorkflowResult, Success, Error

def preview_and_confirm_issue_step(ctx: WorkflowContext) -> WorkflowResult:
    """
    Show a preview of the AI-generated issue and ask for confirmation.
    """
    if not ctx.textual:
        return Error("Textual UI context is not available for this step.")

    issue_title = ctx.get("issue_title")
    issue_body = ctx.get("issue_body")

    if not issue_title or not issue_body:
        return Error("issue_title or issue_body not found in context")

    # Show preview header
    ctx.textual.text("")  # spacing
    ctx.textual.text("AI-Generated Issue Preview", markup="bold")
    ctx.textual.text("")  # spacing

    # Show title
    ctx.textual.text("Title:", markup="bold")
    ctx.textual.text(f"  {issue_title}", markup="cyan")
    ctx.textual.text("")  # spacing

    # Show description
    ctx.textual.text("Description:", markup="bold")
    # Render markdown in a scrollable container
    ctx.textual.markdown(issue_body)

    ctx.textual.text("")  # spacing

    try:
        if not ctx.textual.ask_confirm("Use this AI-generated issue?", default=True):
            return Error("User rejected AI-generated issue")
    except (KeyboardInterrupt, EOFError):
        return Error("User cancelled operation")

    return Success("User confirmed AI-generated issue")
