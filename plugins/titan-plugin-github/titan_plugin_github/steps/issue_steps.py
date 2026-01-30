import ast
from titan_cli.engine.context import WorkflowContext
from titan_cli.engine.results import WorkflowResult, Success, Error, Skip
from ..agents.issue_generator import IssueGeneratorAgent

def ai_suggest_issue_title_and_body_step(ctx: WorkflowContext) -> WorkflowResult:
    """
    Use AI to suggest a title and description for a GitHub issue.
    Auto-categorizes and selects the appropriate template.
    """
    if not ctx.textual:
        return Error("Textual UI context is not available for this step.")

    # Begin step container
    ctx.textual.begin_step("Categorize and Generate Issue")

    if not ctx.ai:
        ctx.textual.text("AI client not available", markup="dim")
        ctx.textual.end_step("skip")
        return Skip("AI client not available")

    issue_body_prompt = ctx.get("issue_body")
    if not issue_body_prompt:
        ctx.textual.text("issue_body not found in context", markup="red")
        ctx.textual.end_step("error")
        return Error("issue_body not found in context")

    ctx.textual.text("Using AI to categorize and generate issue...", markup="dim")

    try:
        # Get available labels from repository for smart mapping
        available_labels = None
        if ctx.github:
            try:
                available_labels = ctx.github.list_labels()
            except Exception:
                # If we can't get labels, continue without filtering
                pass

        # Get template directory from repo path
        template_dir = None
        if ctx.git:
            from pathlib import Path
            template_dir = Path(ctx.git.repo_path) / ".github" / "ISSUE_TEMPLATE"

        issue_generator = IssueGeneratorAgent(ctx.ai, template_dir=template_dir)

        with ctx.textual.loading("Generating issue with AI..."):
            result = issue_generator.generate_issue(issue_body_prompt, available_labels=available_labels)

        # Show category detected
        category = result["category"]
        template_used = result.get("template_used", False)

        ctx.textual.text("")  # spacing
        ctx.textual.text(f"Category detected: {category}", markup="green")

        if template_used:
            ctx.textual.text(f"Using template: {category}.md", markup="cyan")
        else:
            ctx.textual.text(f"No template found for {category}, using default structure", markup="yellow")

        ctx.set("issue_title", result["title"])
        ctx.set("issue_body", result["body"])
        ctx.set("issue_category", category)
        ctx.set("labels", result["labels"])

        ctx.textual.end_step("success")
        return Success(f"AI-generated issue ({category}) created successfully")
    except Exception as e:
        ctx.textual.text(f"Failed to generate issue: {e}", markup="red")
        ctx.textual.end_step("error")
        return Error(f"Failed to generate issue: {e}")


def create_issue_steps(ctx: WorkflowContext) -> WorkflowResult:
    """
    Create a new GitHub issue.
    """
    if not ctx.textual:
        return Error("Textual UI context is not available for this step.")

    # Begin step container
    ctx.textual.begin_step("Create Issue")

    if not ctx.github:
        ctx.textual.text("GitHub client not available", markup="red")
        ctx.textual.end_step("error")
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
        ctx.textual.text("issue_title not found in context", markup="red")
        ctx.textual.end_step("error")
        return Error("issue_title not found in context")

    if not issue_body:
        ctx.textual.text("issue_body not found in context", markup="red")
        ctx.textual.end_step("error")
        return Error("issue_body not found in context")

    # Filter labels to only those that exist in the repository
    if labels and ctx.github:
        try:
            available_labels = ctx.github.list_labels()
            # Filter labels to only include those that exist (case-insensitive)
            filtered_labels = [
                label for label in labels
                if label.lower() in [av_label.lower() for av_label in available_labels]
            ]
            labels = filtered_labels
        except Exception:
            # If we can't validate labels, continue with all labels anyway
            pass

    try:
        ctx.textual.text(f"Creating issue: {issue_title}...", markup="dim")
        issue = ctx.github.create_issue(
            title=issue_title,
            body=issue_body,
            assignees=assignees,
            labels=labels,
        )
        ctx.textual.text("")  # spacing
        ctx.textual.text(f"Successfully created issue #{issue.number}", markup="green")
        ctx.textual.end_step("success")
        return Success(
            f"Successfully created issue #{issue.number}",
            metadata={"issue": issue}
        )
    except Exception as e:
        ctx.textual.text(f"Failed to create issue: {e}", markup="red")
        ctx.textual.end_step("error")
        return Error(f"Failed to create issue: {e}")
