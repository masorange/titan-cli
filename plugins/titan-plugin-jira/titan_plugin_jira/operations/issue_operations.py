"""
Issue operations.

Pure business logic for issue-related operations.
"""

from typing import TYPE_CHECKING

from titan_cli.core.result import ClientResult, ClientSuccess, ClientError

if TYPE_CHECKING:
    from titan_plugin_jira.clients.jira_client import JiraClient
    from titan_plugin_jira.models.view import UITransition


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
