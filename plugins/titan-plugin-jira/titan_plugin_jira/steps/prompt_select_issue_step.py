"""
Prompt user to select an issue from search results
"""

from titan_cli.engine import WorkflowContext, WorkflowResult, Success, Error
from titan_cli.ui.tui.widgets import Panel
from ..messages import msg


def prompt_select_issue_step(ctx: WorkflowContext) -> WorkflowResult:
    """
    Prompt user to select a JIRA issue from search results.

    Inputs (from ctx.data):
        jira_issues (List[JiraTicket]): List of issues from search

    Outputs (saved to ctx.data):
        jira_issue_key (str): Selected issue key
        selected_issue (JiraTicket): Selected issue object
    """
    if not ctx.textual:
        return Error("Textual UI context is not available for this step.")

    # Get issues from previous search
    issues = ctx.get("jira_issues")
    if not issues:
        return Error(msg.Steps.PromptSelectIssue.NO_ISSUES_AVAILABLE)

    if len(issues) == 0:
        return Error(msg.Steps.PromptSelectIssue.NO_ISSUES_AVAILABLE)

    # Prompt user to select issue (issues already displayed in table from previous step)
    ctx.textual.text("")

    try:
        # Ask for selection using text input and validate
        response = ctx.textual.ask_text(
            msg.Steps.PromptSelectIssue.ASK_ISSUE_NUMBER,
            default=""
        )

        if not response or not response.strip():
            return Error(msg.Steps.PromptSelectIssue.NO_ISSUE_SELECTED)

        # Validate it's a number
        try:
            selected_index = int(response.strip())
        except ValueError:
            return Error(f"Invalid input: '{response}' is not a number")

        # Validate it's in range
        if selected_index < 1 or selected_index > len(issues):
            return Error(f"Invalid selection: must be between 1 and {len(issues)}")

        # Convert to 0-based index
        selected_issue = issues[selected_index - 1]

        ctx.textual.text("")
        ctx.textual.mount(
            Panel(
                text=msg.Steps.PromptSelectIssue.ISSUE_SELECTION_CONFIRM.format(
                    key=selected_issue.key,
                    summary=selected_issue.summary
                ),
                panel_type="success"
            )
        )

        return Success(
            msg.Steps.PromptSelectIssue.SELECT_SUCCESS.format(key=selected_issue.key),
            metadata={
                "jira_issue_key": selected_issue.key,
                "selected_issue": selected_issue
            }
        )
    except (KeyboardInterrupt, EOFError):
        return Error("User cancelled issue selection")


__all__ = ["prompt_select_issue_step"]
