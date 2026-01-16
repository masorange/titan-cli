# plugins/titan-plugin-github/titan_plugin_github/steps/prompt_steps.py
from titan_cli.engine.context import WorkflowContext
from titan_cli.engine.results import WorkflowResult, Success, Error, Skip
from ..messages import msg


def prompt_for_pr_title_step(ctx: WorkflowContext) -> WorkflowResult:
    """
    Interactively prompts the user for a Pull Request title.
    Skips if pr_title already exists.

    Requires:
        ctx.textual: Textual UI components.

    Outputs (saved to ctx.data):
        pr_title (str): The title entered by the user.

    Returns:
        Success: If the title was captured successfully.
        Error: If the user cancels or the title is empty.
        Skip: If pr_title already exists.
    """
    if not ctx.textual:
        return Error("Textual UI context is not available for this step.")

    # Skip if title already exists (e.g., from AI generation)
    if ctx.get("pr_title"):
        return Skip("PR title already provided, skipping manual prompt.")

    try:
        title = ctx.textual.ask_text(msg.Prompts.ENTER_PR_TITLE)
        if not title:
            return Error("PR title cannot be empty.")
        return Success("PR title captured", metadata={"pr_title": title})
    except (KeyboardInterrupt, EOFError):
        return Error("User cancelled.")
    except Exception as e:
        return Error(f"Failed to prompt for PR title: {e}", exception=e)


def prompt_for_pr_body_step(ctx: WorkflowContext) -> WorkflowResult:
    """
    Interactively prompts the user for a Pull Request body.
    Skips if pr_body already exists.

    Requires:
        ctx.textual: Textual UI components.

    Outputs (saved to ctx.data):
        pr_body (str): The body/description entered by the user.

    Returns:
        Success: If the body was captured successfully.
        Error: If the user cancels.
        Skip: If pr_body already exists.
    """
    if not ctx.textual:
        return Error("Textual UI context is not available for this step.")

    # Skip if body already exists (e.g., from AI generation)
    if ctx.get("pr_body"):
        return Skip("PR body already provided, skipping manual prompt.")

    try:
        body = ctx.textual.ask_multiline(msg.Prompts.ENTER_PR_BODY, default="")
        # Body can be empty
        return Success("PR body captured", metadata={"pr_body": body})
    except (KeyboardInterrupt, EOFError):
        return Error("User cancelled.")
    except Exception as e:
        return Error(f"Failed to prompt for PR body: {e}", exception=e)


def prompt_for_issue_body_step(ctx: WorkflowContext) -> WorkflowResult:
    """
    Interactively prompts the user for a GitHub issue body.
    Skips if issue_body already exists.

    Requires:
        ctx.textual: Textual UI components.

    Outputs (saved to ctx.data):
        issue_body (str): The body/description entered by the user.

    Returns:
        Success: If the body was captured successfully.
        Error: If the user cancels.
        Skip: If issue_body already exists.
    """
    if not ctx.textual:
        return Error("Textual UI context is not available for this step.")

    # Skip if body already exists (e.g., from AI generation)
    if ctx.get("issue_body"):
        return Skip("Issue body already provided, skipping manual prompt.")

    try:
        body = ctx.textual.ask_multiline(msg.Prompts.ENTER_ISSUE_BODY, default="")
        # Body can be empty
        return Success("Issue body captured", metadata={"issue_body": body})
    except (KeyboardInterrupt, EOFError):
        return Error("User cancelled.")
    except Exception as e:
        return Error(f"Failed to prompt for issue body: {e}", exception=e)


def prompt_for_self_assign_step(ctx: WorkflowContext) -> WorkflowResult:
    """
    Asks the user if they want to assign the issue to themselves.
    """
    if not ctx.github:
        return Error("GitHub client not available")

    if not ctx.views:
        return Error("UI components not available")

    try:
        if ctx.views.prompts.ask_confirm(msg.Prompts.ASSIGN_TO_SELF, default=True):
            current_user = ctx.github.get_current_user()
            assignees = ctx.get("assignees", [])
            if current_user not in assignees:
                assignees.append(current_user)
            ctx.set("assignees", assignees)
            return Success(f"Issue will be assigned to {current_user}")
        return Success("Issue will not be assigned to current user")
    except (KeyboardInterrupt, EOFError):
        return Error("User cancelled.")
    except Exception as e:
        return Error(f"Failed to prompt for self-assign: {e}", exception=e)


def prompt_for_labels_step(ctx: WorkflowContext) -> WorkflowResult:
    """
    Prompts the user to select labels for the issue.
    """
    if not ctx.textual:
        return Error("Textual UI context is not available for this step.")

    if not ctx.github:
        return Error("GitHub client not available")

    try:
        available_labels = ctx.github.list_labels()
        if not available_labels:
            return Skip("No labels found in the repository.")

        # Show available labels
        ctx.textual.text(f"Available labels: {', '.join(available_labels)}", markup="dim")

        # Get default labels as comma-separated string
        existing_labels = ctx.get("labels", [])
        default_value = ",".join(existing_labels) if existing_labels else ""

        # TODO: Implement multi-select in Textual - for now use comma-separated input
        labels_input = ctx.textual.ask_text(
            f"{msg.Prompts.SELECT_LABELS} (comma-separated)",
            default=default_value
        )

        # Parse comma-separated labels
        if labels_input:
            selected_labels = [label.strip() for label in labels_input.split(",") if label.strip()]
        else:
            selected_labels = []

        ctx.set("labels", selected_labels)
        return Success("Labels selected")
    except (KeyboardInterrupt, EOFError):
        return Error("User cancelled.")
    except Exception as e:
        return Error(f"Failed to prompt for labels: {e}", exception=e)
