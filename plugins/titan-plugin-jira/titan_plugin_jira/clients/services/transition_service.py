"""
Transition Service

Handles workflow transition operations.
Network → NetworkModel → UIModel → ClientResult
"""

from typing import List, Optional

from titan_cli.core.result import ClientResult, ClientSuccess, ClientError
from titan_cli.core.logging import log_client_operation

from ..network import JiraNetwork
from ...models import (
    NetworkJiraTransition,
    NetworkJiraStatus,
    NetworkJiraStatusCategory,
    UIJiraTransition,
    from_network_transition,
)
from ...exceptions import JiraAPIError


class TransitionService:
    """
    Service for Jira transition operations.

    PRIVATE - only used by JiraClient.
    """

    def __init__(self, network: JiraNetwork):
        self.network = network

    @log_client_operation()
    def get_transitions(self, issue_key: str) -> ClientResult[List[UIJiraTransition]]:
        """
        Get available transitions for an issue.

        Args:
            issue_key: Issue key

        Returns:
            ClientResult[List[UIJiraTransition]]
        """
        try:
            # 1. Network call
            data = self.network.make_request("GET", f"issue/{issue_key}/transitions")

            # 2. Parse and map each transition
            ui_transitions = []
            for trans_data in data.get("transitions", []):
                network_transition = self._parse_network_transition(trans_data)
                ui_transition = from_network_transition(network_transition)
                ui_transitions.append(ui_transition)

            # 3. Wrap in Result
            return ClientSuccess(
                data=ui_transitions,
                message=f"Found {len(ui_transitions)} transitions"
            )

        except JiraAPIError as e:
            return ClientError(
                error_message=f"Failed to get transitions for {issue_key}: {e.message}",
                error_code="GET_TRANSITIONS_ERROR"
            )

    @log_client_operation()
    def transition_issue(
        self,
        issue_key: str,
        new_status: str,
        comment: Optional[str] = None
    ) -> ClientResult[None]:
        """
        Transition issue to new status.

        Args:
            issue_key: Issue key
            new_status: Target status name
            comment: Optional comment to add

        Returns:
            ClientResult[None] (operation success/failure)
        """
        try:
            # 1. Get available transitions
            transitions_result = self.get_transitions(issue_key)

            # Unpack result
            if isinstance(transitions_result, ClientError):
                return transitions_result

            transitions = transitions_result.data

            # 2. Find transition to target status
            transition_id = None
            for trans in transitions:
                if trans.to_status.lower() == new_status.lower():
                    transition_id = trans.id
                    break

            if not transition_id:
                available = [t.to_status for t in transitions]
                return ClientError(
                    error_message=f"Cannot transition to '{new_status}'. Available: {', '.join(available)}",
                    error_code="INVALID_TRANSITION",
                    log_level="warning"
                )

            # 3. Build payload
            payload = {
                "transition": {"id": transition_id}
            }

            # Add comment if provided
            if comment:
                payload["update"] = {
                    "comment": [{
                        "add": {
                            "body": {
                                "type": "doc",
                                "version": 1,
                                "content": [{
                                    "type": "paragraph",
                                    "content": [{"type": "text", "text": comment}]
                                }]
                            }
                        }
                    }]
                }

            # 4. Network call
            self.network.make_request("POST", f"issue/{issue_key}/transitions", json=payload)

            # 5. Wrap in Result
            return ClientSuccess(
                data=None,
                message=f"Transitioned {issue_key} to {new_status}"
            )

        except JiraAPIError as e:
            return ClientError(
                error_message=f"Failed to transition {issue_key} to {new_status}: {e.message}",
                error_code="TRANSITION_ERROR"
            )

    def _parse_network_transition(self, data: dict) -> NetworkJiraTransition:
        """Parse transition data from API response"""
        # Parse target status
        to_status = None
        if data.get("to"):
            to_data = data["to"]

            status_category = None
            if to_data.get("statusCategory"):
                cat_data = to_data["statusCategory"]
                status_category = NetworkJiraStatusCategory(
                    id=cat_data.get("id", ""),
                    name=cat_data.get("name", ""),
                    key=cat_data.get("key", ""),
                    colorName=cat_data.get("colorName"),
                )

            to_status = NetworkJiraStatus(
                id=to_data.get("id", ""),
                name=to_data.get("name", ""),
                description=to_data.get("description"),
                statusCategory=status_category,
            )

        return NetworkJiraTransition(
            id=data["id"],
            name=data["name"],
            to=to_status,
            hasScreen=data.get("hasScreen", False),
        )


__all__ = ["TransitionService"]
