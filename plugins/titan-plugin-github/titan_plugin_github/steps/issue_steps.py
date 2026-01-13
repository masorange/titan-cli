import ast
from titan_cli.engine.context import WorkflowContext
from titan_cli.engine.results import WorkflowResult, Success, Error, Skip
from ..agents.issue_generator import IssueGeneratorAgent

def ai_suggest_issue_title_and_body_step(ctx: WorkflowContext) -> WorkflowResult:
    """
    Use AI to suggest a title and description for a GitHub issue.
    Auto-categorizes and selects the appropriate template.
    """
    if not ctx.ai:
        return Skip("AI client not available")

    if not ctx.ui:
        return Error("UI components not available")

    issue_body_prompt = ctx.get("issue_body")
    if not issue_body_prompt:
        return Error("issue_body not found in context")

    ctx.ui.text.info("Using AI to categorize and generate issue...")

    try:
        issue_generator = IssueGeneratorAgent(ctx.ai)
        result = issue_generator.generate_issue(issue_body_prompt)

        # Show category detected
        category = result["category"]
        template_used = result.get("template_used", False)

        if ctx.ui:
            ctx.ui.text.success(f"Category detected: {category}")
            if template_used:
                ctx.ui.text.info(f"Using template: {category}.md")
            else:
                ctx.ui.text.warning(f"No template found for {category}, using default structure")

        ctx.set("issue_title", result["title"])
        ctx.set("issue_body", result["body"])
        ctx.set("issue_category", category)
        ctx.set("labels", result["labels"])

        return Success(f"AI-generated issue ({category}) created successfully")
    except Exception as e:
        return Error(f"Failed to generate issue: {e}")


def create_issue_steps(ctx: WorkflowContext) -> WorkflowResult:
    """
    Create a new GitHub issue.
    """
    if not ctx.github:
        return Error("GitHub client not available")

    issue_title = ctx.get("issue_title")
    issue_body = ctx.get("issue_body")
    assignees = ctx.get("assignees", [])
    labels = ctx.get("labels", [])

    # Safely parse string representations to lists
    if isinstance(assignees, str):
        try:
            assignees = ast.literal_eval(assignees)
        except (ValueError, SyntaxError):
            assignees = []

    if isinstance(labels, str):
        try:
            labels = ast.literal_eval(labels)
        except (ValueError, SyntaxError):
            labels = []

    # Ensure they are lists
    if not isinstance(assignees, list):
        assignees = []
    if not isinstance(labels, list):
        labels = []

    if not issue_title:
        return Error("issue_title not found in context")

    if not issue_body:
        return Error("issue_body not found in context")

    # Validate that labels exist in GitHub repository
    if labels and ctx.github:
        try:
            available_labels = ctx.github.list_labels()
            invalid_labels = [label for label in labels if label not in available_labels]

            if invalid_labels:
                return Error(
                    f"Invalid labels: {', '.join(invalid_labels)}. "
                    f"Available labels: {', '.join(available_labels[:10])}"
                )
        except Exception:
            # If we can't validate labels, continue anyway
            pass

    try:
        issue = ctx.github.create_issue(
            title=issue_title,
            body=issue_body,
            assignees=assignees,
            labels=labels,
        )
        return Success(
            f"Successfully created issue #{issue.number}",
            metadata={"issue": issue}
        )
    except Exception as e:
        return Error(f"Failed to create issue: {e}")
