"""
Create Generic Issue Step

Creates the issue in Jira with all collected information.
"""

from titan_cli.engine import WorkflowContext, WorkflowResult, Success, Error
from titan_cli.core.result import ClientSuccess, ClientError
from titan_cli.ui.tui.widgets import Panel
from titan_plugin_jira.constants import (
    StepTitles,
    ErrorMessages,
    SuccessMessages,
    InfoMessages,
)
from titan_plugin_jira.operations import transition_issue_to_ready_for_dev


def create_generic_issue(ctx: WorkflowContext) -> WorkflowResult:
    """
    Create the issue in Jira.

    Requires:
    - ctx.data["title"]
    - ctx.data["final_description"]
    - ctx.data["issue_type"]
    - ctx.data["priority"]
    - ctx.data["auto_assign"] (bool)
    - ctx.data["assignee_id"] (optional, if auto_assign is True)

    Stores in:
    - ctx.data["created_issue"] = UIJiraIssue

    Returns:
        WorkflowResult
    """
    ctx.textual.begin_step(StepTitles.CREATE_ISSUE)

    # Get required data
    title = ctx.data.get("title")
    description = ctx.data.get("final_description")
    issue_type = ctx.data.get("issue_type")
    priority = ctx.data.get("priority")
    auto_assign = ctx.data.get("auto_assign", False)
    assignee_id = ctx.data.get("assignee_id")

    # Validate required data
    if not all([title, description, issue_type, priority]):
        ctx.textual.mount(Panel(ErrorMessages.MISSING_REQUIRED_DATA, panel_type="error"))
        ctx.textual.end_step("error")
        return Error("missing_required_data")

    # Get project key
    project_key = ctx.jira.project_key
    if not project_key:
        ctx.textual.mount(Panel(ErrorMessages.NO_PROJECT_CONFIGURED, panel_type="error"))
        ctx.textual.end_step("error")
        return Error("no_project_configured")

    ctx.textual.markdown(f"## 🚀 {InfoMessages.CREATING_ISSUE_HEADING}")
    ctx.textual.text("")
    ctx.textual.dim_text(InfoMessages.PROJECT_LABEL.format(project=project_key))
    ctx.textual.dim_text(InfoMessages.TYPE_LABEL.format(type=issue_type))
    ctx.textual.dim_text(InfoMessages.PRIORITY_LABEL.format(priority=priority))
    ctx.textual.text("")

    # Create issue using client method (NOT service directly)
    with ctx.textual.loading(InfoMessages.CREATING_ISSUE):
        result = ctx.jira.create_issue(
            issue_type=issue_type,
            summary=title,
            description=description,
            project=project_key,
            assignee=assignee_id if auto_assign and assignee_id else None,
            priority=priority,
        )

    match result:
        case ClientSuccess(data=issue):
            # Store created issue
            ctx.data["created_issue"] = issue

            ctx.textual.text("")
            ctx.textual.success_text(SuccessMessages.ISSUE_CREATED.format(key=issue.key))
            ctx.textual.text("")

            # Show issue details
            ctx.textual.mount(
                Panel(
                    f"**Issue:** {issue.key}\n"
                    f"**Title:** {issue.summary}\n"
                    f"**Type:** {issue.issue_type}\n"
                    f"**Status:** {issue.status_icon} {issue.status}\n"
                    f"**Priority:** {issue.priority_icon} {issue.priority}",
                    panel_type="success",
                )
            )

            # Try to transition to "Ready to Dev" if possible (best-effort)
            _attempt_transition_to_ready_for_dev(ctx, issue.key)

            ctx.textual.text("")
            ctx.textual.end_step("success")

            return Success(
                f"Issue created: {issue.key}", metadata={"issue_key": issue.key}
            )

        case ClientError(error_message=err):
            ctx.textual.mount(
                Panel(ErrorMessages.FAILED_TO_CREATE_ISSUE.format(error=err), panel_type="error")
            )
            ctx.textual.end_step("error")
            return Error(f"failed_to_create_issue: {err}")


def _attempt_transition_to_ready_for_dev(ctx: WorkflowContext, issue_key: str):
    """
    Attempt to transition issue to "Ready to Dev" status (best-effort).

    This operation is NOT critical - if it fails, we just log it and continue.

    Args:
        ctx: Workflow context
        issue_key: Issue key (e.g., "PROJ-123")
    """
    # Use operation for business logic
    transition_result = transition_issue_to_ready_for_dev(ctx.jira, issue_key)

    match transition_result:
        case ClientSuccess():
            # Get transition details to show user
            find_result = ctx.jira.get_transitions(issue_key)
            match find_result:
                case ClientSuccess(data=transitions):
                    ready_transition = next(
                        (
                            t
                            for t in transitions
                            if "ready" in t.name.lower() and "dev" in t.name.lower()
                        ),
                        None,
                    )
                    if ready_transition:
                        ctx.textual.dim_text(
                            InfoMessages.TRANSITIONING_TO.format(
                                status=ready_transition.to_status
                            )
                        )
                        ctx.textual.success_text(
                            SuccessMessages.STATUS_CHANGED.format(
                                status=ready_transition.to_status
                            )
                        )
                case ClientError():
                    pass  # Ignore, not critical

        case ClientError(error_message=err):
            # Check if it's "not found" error (expected)
            if "not found" in err.lower() or "TRANSITION_NOT_FOUND" in str(err):
                ctx.textual.dim_text(InfoMessages.NO_READY_TO_DEV_TRANSITION)
            else:
                # Unexpected error, log it
                ctx.textual.dim_text(ErrorMessages.FAILED_TO_TRANSITION.format(error=err))
