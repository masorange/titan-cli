"""
Get JIRA issue details step
"""

from titan_cli.engine import WorkflowContext, WorkflowResult, Success, Error
from titan_cli.core.result import ClientSuccess, ClientError
from ..messages import msg


def get_issue_step(ctx: WorkflowContext) -> WorkflowResult:
    """
    Get JIRA issue details by key.

    Inputs (from ctx.data):
        jira_issue_key (str): JIRA issue key (e.g., "PROJ-123")
        expand (list[str], optional): Additional fields to expand

    Outputs (saved to ctx.data):
        jira_issue (UIJiraIssue): Issue details

    Returns:
        Success: Issue retrieved
        Error: Failed to get issue
    """
    if not ctx.textual:
        return Error("Textual UI context is not available for this step.")

    # Begin step container
    ctx.textual.begin_step("Get Full Issue Details")

    # Check if JIRA client is available
    if not ctx.jira:
        ctx.textual.error_text(msg.Plugin.CLIENT_NOT_AVAILABLE_IN_CONTEXT)
        ctx.textual.end_step("error")
        return Error(msg.Plugin.CLIENT_NOT_AVAILABLE_IN_CONTEXT)

    # Get issue key
    issue_key = ctx.get("jira_issue_key")
    if not issue_key:
        ctx.textual.error_text("JIRA issue key is required")
        ctx.textual.end_step("error")
        return Error("JIRA issue key is required")

    # Get optional expand fields
    expand = ctx.get("expand")

    # Get issue with loading indicator
    with ctx.textual.loading(msg.Steps.GetIssue.GETTING_ISSUE.format(issue_key=issue_key)):
        result = ctx.jira.get_issue(key=issue_key, expand=expand)

    # Pattern match on Result
    match result:
        case ClientSuccess(data=issue):
            # Show success
            ctx.textual.text("")  # spacing
            ctx.textual.success_text(msg.Steps.GetIssue.GET_SUCCESS.format(issue_key=issue_key))

            # Show issue details (UI model has pre-formatted fields)
            ctx.textual.primary_text(f"  {issue.issue_type_icon} {issue.summary}")
            ctx.textual.text(f"  Status: {issue.status_icon} {issue.status}")
            ctx.textual.text(f"  Type: {issue.issue_type}")
            ctx.textual.text(f"  Assignee: {issue.assignee}")
            ctx.textual.text(f"  Priority: {issue.priority_icon} {issue.priority}")
            ctx.textual.text(f"  Created: {issue.formatted_created_at}")
            ctx.textual.text("")

            ctx.textual.end_step("success")
            return Success(
                msg.Steps.GetIssue.GET_SUCCESS.format(issue_key=issue_key),
                metadata={"jira_issue": issue}
            )

        case ClientError(error_message=err, error_code=code):
            # Handle error
            if code == "ISSUE_NOT_FOUND":
                error_msg = msg.Steps.GetIssue.ISSUE_NOT_FOUND.format(issue_key=issue_key)
            else:
                error_msg = msg.Steps.GetIssue.GET_FAILED.format(e=err)

            ctx.textual.error_text(error_msg)
            ctx.textual.end_step("error")
            return Error(error_msg)


__all__ = ["get_issue_step"]
