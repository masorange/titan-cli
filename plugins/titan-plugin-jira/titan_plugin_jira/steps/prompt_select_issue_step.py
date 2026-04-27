"""
Prompt user to select an issue from search results
"""

from titan_cli.engine import WorkflowContext, WorkflowResult, Success, Error
from ..messages import msg


def _interaction(ctx: WorkflowContext):
    """Return the preferred interaction surface, keeping textual compatibility."""
    return getattr(ctx, "interaction", None) or getattr(ctx, "textual", None)


def prompt_select_issue_step(ctx: WorkflowContext) -> WorkflowResult:
    """
    Prompt user to select a JIRA issue from search results.

    Inputs (from ctx.data):
        jira_issues (List[JiraTicket]): List of issues from search

    Outputs (saved to ctx.data):
        jira_issue_key (str): Selected issue key
        selected_issue (JiraTicket): Selected issue object

    Returns:
        Success: If the user selects a valid issue.
        Error: If there are no issues, the selection is invalid, or the prompt is cancelled.
    """
    ui = _interaction(ctx)
    if not ui:
        return Error("Interaction context is not available for this step.")

    # Begin step container
    ui.begin_step("Select Issue to Analyze")

    # Get issues from previous search
    issues = ctx.get("jira_issues")
    if not issues:
        ui.error_text(msg.Steps.PromptSelectIssue.NO_ISSUES_AVAILABLE)
        ui.end_step("error")
        return Error(msg.Steps.PromptSelectIssue.NO_ISSUES_AVAILABLE)

    if len(issues) == 0:
        ui.error_text(msg.Steps.PromptSelectIssue.NO_ISSUES_AVAILABLE)
        ui.end_step("error")
        return Error(msg.Steps.PromptSelectIssue.NO_ISSUES_AVAILABLE)

    # Prompt user to select issue (issues already displayed in table from previous step)
    ui.text("")

    try:
        # Ask for selection using text input and validate
        response = ui.ask_text(
            msg.Steps.PromptSelectIssue.ASK_ISSUE_NUMBER,
            default=""
        )

        if not response or not response.strip():
            ui.error_text(msg.Steps.PromptSelectIssue.NO_ISSUE_SELECTED)
            ui.end_step("error")
            return Error(msg.Steps.PromptSelectIssue.NO_ISSUE_SELECTED)

        # Validate it's a number
        try:
            selected_index = int(response.strip())
        except ValueError:
            ui.error_text(f"Invalid input: '{response}' is not a number")
            ui.end_step("error")
            return Error(f"Invalid input: '{response}' is not a number")

        # Validate it's in range
        if selected_index < 1 or selected_index > len(issues):
            ui.error_text(f"Invalid selection: must be between 1 and {len(issues)}")
            ui.end_step("error")
            return Error(f"Invalid selection: must be between 1 and {len(issues)}")

        # Convert to 0-based index
        selected_issue = issues[selected_index - 1]

        ui.text("")
        ui.success_text(
            msg.Steps.PromptSelectIssue.ISSUE_SELECTION_CONFIRM.format(
                key=selected_issue.key,
                summary=selected_issue.summary
            )
        )

        ui.end_step("success")
        return Success(
            msg.Steps.PromptSelectIssue.SELECT_SUCCESS.format(key=selected_issue.key),
            metadata={
                "jira_issue_key": selected_issue.key,
                "selected_issue": selected_issue
            }
        )
    except (KeyboardInterrupt, EOFError):
        ui.error_text("User cancelled issue selection")
        ui.end_step("error")
        return Error("User cancelled issue selection")


__all__ = ["prompt_select_issue_step"]
