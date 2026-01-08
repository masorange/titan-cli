from titan_cli.engine.context import WorkflowContext
from titan_cli.engine.results import WorkflowResult, Success, Error, Skip
from titan_cli.ai.models import AIMessage

def ai_suggest_issue_title_and_body(ctx: WorkflowContext) -> WorkflowResult:
    """
    Use AI to suggest a title and description for a GitHub issue.
    """
    if not ctx.ai:
        return Skip("AI client not available")

    if not ctx.ui:
        return Error("UI components not available")

    issue_body_prompt = ctx.get("issue_body")
    if not issue_body_prompt:
        return Error("issue_body not found in context")

    ctx.ui.text.info("Using AI to generate issue title and description...")

    try:
        prompt = f"Generate a GitHub issue title and description for the following content:\n\n{issue_body_prompt}"
        messages = [AIMessage(role="user", content=prompt)]
        response = ctx.ai.generate(messages)
        
        # Assuming the AI returns a response in the format "TITLE: ...\nDESCRIPTION: ..."
        parts = response.content.split("DESCRIPTION:", 1)
        title = parts[0].replace("TITLE:", "").strip()
        body = parts[1].strip()

        ctx.set("issue_title", title)
        ctx.set("issue_body", body)
        return Success("AI-generated issue title and description created")
    except Exception as e:
        return Error(f"Failed to generate issue title and description: {e}")


def create_issue(ctx: WorkflowContext) -> WorkflowResult:
    """
    Create a new GitHub issue.
    """
    if not ctx.github:
        return Error("GitHub client not available")

    issue_title = ctx.get("issue_title")
    issue_body = ctx.get("issue_body")
    assignees = ctx.get("assignees")
    labels = ctx.get("labels")

    if not issue_title:
        return Error("issue_title not found in context")

    if not issue_body:
        return Error("issue_body not found in context")

    try:
        issue = ctx.github.create_issue(
            title=issue_title,
            body=issue_body,
            assignees=assignees,
            labels=labels,
        )
        ctx.set("issue", issue)
        return Success(f"Successfully created issue #{issue.number}")
    except Exception as e:
        return Error(f"Failed to create issue: {e}")
