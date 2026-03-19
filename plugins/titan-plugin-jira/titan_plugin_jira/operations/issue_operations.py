"""
Issue operations.

Pure business logic for issue-related operations.
"""

from typing import TYPE_CHECKING, Optional

from titan_cli.core.result import ClientResult, ClientSuccess, ClientError

if TYPE_CHECKING:
    from titan_plugin_jira.clients.jira_client import JiraClient
    from titan_plugin_jira.models.view import UITransition
    from titan_plugin_jira.models.network.rest.issue_type import NetworkJiraIssueType


def find_ready_to_dev_transition(
    jira_client: "JiraClient", issue_key: str
) -> ClientResult["UITransition"]:
    """
    Find "Ready to Dev" transition for an issue.

    Args:
        jira_client: Jira client instance
        issue_key: Issue key (e.g., "PROJ-123")

    Returns:
        ClientResult with UITransition if found, error otherwise
    """
    transitions_result = jira_client.get_transitions(issue_key)

    match transitions_result:
        case ClientSuccess(data=transitions):
            # Look for "Ready to Dev" transition
            ready_transition = next(
                (
                    t
                    for t in transitions
                    if "ready" in t.name.lower() and "dev" in t.name.lower()
                ),
                None,
            )

            if ready_transition:
                return ClientSuccess(data=ready_transition)

            return ClientError(
                error_message="No 'Ready to Dev' transition found",
                error_code="TRANSITION_NOT_FOUND",
            )

        case ClientError() as error:
            return error


def transition_issue_to_ready_for_dev(
    jira_client: "JiraClient", issue_key: str
) -> ClientResult[None]:
    """
    Attempt to transition issue to "Ready to Dev" status.

    This is a best-effort operation:
    - If transition is found and succeeds, returns success
    - If transition is not found or fails, returns error (not critical)

    Args:
        jira_client: Jira client instance
        issue_key: Issue key (e.g., "PROJ-123")

    Returns:
        ClientResult indicating success or failure
    """
    # Find transition
    find_result = find_ready_to_dev_transition(jira_client, issue_key)

    match find_result:
        case ClientSuccess(data=transition):
            # Execute transition
            return jira_client.transition_issue(
                issue_key=issue_key, new_status=transition.to_status
            )

        case ClientError() as error:
            return error


def find_issue_type_by_name(
    jira_client: "JiraClient", project_key: str, issue_type_name: str
) -> ClientResult["NetworkJiraIssueType"]:
    """
    Find issue type by name in a project.

    Args:
        jira_client: Jira client instance
        project_key: Project key
        issue_type_name: Issue type name to search (case-insensitive)

    Returns:
        ClientResult with NetworkJiraIssueType if found, error otherwise
    """
    issue_types_result = jira_client.get_issue_types(project_key)

    match issue_types_result:
        case ClientSuccess(data=issue_types):
            # Search for issue type (case-insensitive)
            issue_type = next(
                (it for it in issue_types if it.name.lower() == issue_type_name.lower()),
                None,
            )

            if issue_type:
                return ClientSuccess(data=issue_type)

            # Not found - return helpful error with available types
            available = [it.name for it in issue_types]
            return ClientError(
                error_message=f"Issue type '{issue_type_name}' not found. Available: {', '.join(available)}",
                error_code="INVALID_ISSUE_TYPE",
            )

        case ClientError() as error:
            return error


def prepare_epic_name(issue_type: "NetworkJiraIssueType", summary: str) -> Optional[str]:
    """
    Prepare Epic Name field if issue type is Epic.

    Jira requires Epic Name as a custom field when creating Epics.

    Args:
        issue_type: Issue type object
        summary: Issue summary

    Returns:
        Epic name (same as summary) if Epic type, None otherwise
    """
    if issue_type.name.lower() == "epic":
        return summary
    return None


def find_subtask_issue_type(
    jira_client: "JiraClient", project_key: str
) -> ClientResult["NetworkJiraIssueType"]:
    """
    Find subtask issue type for a project.

    Args:
        jira_client: Jira client instance
        project_key: Project key

    Returns:
        ClientResult with NetworkJiraIssueType if found, error otherwise
    """
    issue_types_result = jira_client.get_issue_types(project_key)

    match issue_types_result:
        case ClientSuccess(data=issue_types):
            # Find first subtask type
            subtask_type = next((it for it in issue_types if it.subtask), None)

            if subtask_type:
                return ClientSuccess(data=subtask_type)

            return ClientError(
                error_message="No subtask issue type found for project",
                error_code="NO_SUBTASK_TYPE",
            )

        case ClientError() as error:
            return error
