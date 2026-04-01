"""
Issue operations.

Pure business logic for issue-related operations.
"""

from typing import Optional

from titan_cli.core.result import ClientResult, ClientSuccess, ClientError


def find_ready_to_dev_transition(jira_client, issue_key: str):
    """
    Find "Ready to Dev" transition for an issue.

    Args:
        jira_client: Jira client instance
        issue_key: Issue key (e.g., "PROJ-123")

    Returns:
        UITransition if found

    Raises:
        Exception: If transition not found or API call fails
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
                return ready_transition

            raise Exception("No 'Ready to Dev' transition found")

        case ClientError(error_message=err):
            raise Exception(f"Failed to get transitions: {err}")


def transition_issue_to_ready_for_dev(jira_client, issue_key: str):
    """
    Attempt to transition issue to "Ready to Dev" status.

    Args:
        jira_client: Jira client instance
        issue_key: Issue key (e.g., "PROJ-123")

    Returns:
        UITransition object with transition details

    Raises:
        Exception: If transition not found or execution fails
    """
    # Find transition (raises if not found)
    transition = find_ready_to_dev_transition(jira_client, issue_key)

    # Execute transition
    result = jira_client.transition_issue(
        issue_key=issue_key, new_status=transition.to_status
    )

    match result:
        case ClientSuccess():
            return transition
        case ClientError(error_message=err):
            raise Exception(f"Failed to transition issue: {err}")


def find_issue_type_by_name(jira_client, project_key: str, issue_type_name: str):
    """
    Find issue type by name in a project.

    Args:
        jira_client: Jira client instance
        project_key: Project key
        issue_type_name: Issue type name to search (case-insensitive)

    Returns:
        UIJiraIssueType if found

    Raises:
        Exception: If issue type not found or API call fails
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
                return issue_type

            # Not found - raise with available types
            available = [it.name for it in issue_types]
            raise Exception(
                f"Issue type '{issue_type_name}' not found. Available: {', '.join(available)}"
            )

        case ClientError(error_message=err):
            raise Exception(f"Failed to get issue types: {err}")


def find_subtask_issue_type(jira_client, project_key: str):
    """
    Find subtask issue type for a project.

    Args:
        jira_client: Jira client instance
        project_key: Project key

    Returns:
        UIJiraIssueType if found

    Raises:
        Exception: If subtask type not found or API call fails
    """
    issue_types_result = jira_client.get_issue_types(project_key)

    match issue_types_result:
        case ClientSuccess(data=issue_types):
            # Find first subtask type
            subtask_type = next((it for it in issue_types if it.subtask), None)

            if subtask_type:
                return subtask_type

            raise Exception("No subtask issue type found for project")

        case ClientError(error_message=err):
            raise Exception(f"Failed to get issue types: {err}")
