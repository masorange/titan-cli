from titan_cli.engine.context import WorkflowContext
from titan_cli.engine.results import WorkflowResult, Success, Error
from rich.markdown import Markdown

def preview_and_confirm_issue_step(ctx: WorkflowContext) -> WorkflowResult:
    """
    Show a preview of the AI-generated issue and ask for confirmation.
    """
    if not ctx.ui:
        return Error("UI components not available")

    issue_title = ctx.get("issue_title")
    issue_body = ctx.get("issue_body")

    if not issue_title or not issue_body:
        return Error("issue_title or issue_body not found in context")

    ctx.ui.panel.print(
        Markdown(f"[bold]Title:[/] {issue_title}\n\n[bold]Body:[/]\n{issue_body}"),
        title="AI-Generated Issue",
        panel_type="info",
    )

    if not ctx.views.prompts.ask_confirm("Use this AI-generated issue?"):
        return Error("User rejected AI-generated issue")

    return Success("User confirmed AI-generated issue")
