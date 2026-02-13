"""
Metadata Service

Handles Jira metadata operations (issue types, statuses, etc.).
Network → NetworkModel → Result
"""

from typing import List, Dict, Any

from titan_cli.core.result import ClientResult, ClientSuccess, ClientError

from ..network import JiraNetwork
from ...models import NetworkJiraIssueType
from ...exceptions import JiraAPIError


class MetadataService:
    """
    Service for Jira metadata operations.

    PRIVATE - only used by JiraClient.
    Returns Network models (no UI mapping needed for metadata).
    """

    def __init__(self, network: JiraNetwork):
        self.network = network

    def get_issue_types(self, project_key: str) -> ClientResult[List[NetworkJiraIssueType]]:
        """
        Get issue types for a project.

        Args:
            project_key: Project key

        Returns:
            ClientResult[List[NetworkJiraIssueType]]
        """
        try:
            # 1. Get project (includes issue types)
            project_data = self.network.make_request("GET", f"project/{project_key}")

            # 2. Parse issue types
            issue_types = []
            for it_data in project_data.get("issueTypes", []):
                issue_types.append(NetworkJiraIssueType(
                    id=it_data.get("id", ""),
                    name=it_data.get("name", ""),
                    description=it_data.get("description"),
                    subtask=it_data.get("subtask", False),
                    iconUrl=it_data.get("iconUrl"),
                ))

            # 3. Wrap in Result
            return ClientSuccess(
                data=issue_types,
                message=f"Found {len(issue_types)} issue types"
            )

        except JiraAPIError as e:
            return ClientError(
                error_message=str(e),
                error_code="GET_ISSUE_TYPES_ERROR"
            )

    def list_statuses(self, project_key: str) -> ClientResult[List[Dict[str, Any]]]:
        """
        List all available statuses for a project.

        Args:
            project_key: Project key

        Returns:
            ClientResult[List[Dict]] with status info
        """
        try:
            # 1. Network call
            data = self.network.make_request("GET", f"project/{project_key}/statuses")

            # 2. Extract unique statuses
            statuses = []
            seen_names = set()

            for issue_type_data in data:
                for status in issue_type_data.get("statuses", []):
                    status_name = status.get("name")
                    if status_name and status_name not in seen_names:
                        statuses.append({
                            "id": status.get("id"),
                            "name": status_name,
                            "description": status.get("description"),
                            "category": status.get("statusCategory", {}).get("name")
                        })
                        seen_names.add(status_name)

            # 3. Wrap in Result
            return ClientSuccess(
                data=statuses,
                message=f"Found {len(statuses)} statuses"
            )

        except JiraAPIError as e:
            return ClientError(
                error_message=str(e),
                error_code="LIST_STATUSES_ERROR"
            )

    def get_current_user(self) -> ClientResult[Dict[str, Any]]:
        """
        Get current authenticated user info.

        Returns:
            ClientResult[Dict] with user info
        """
        try:
            data = self.network.make_request("GET", "myself")
            return ClientSuccess(
                data=data,
                message="Current user retrieved"
            )

        except JiraAPIError as e:
            return ClientError(
                error_message=str(e),
                error_code="GET_USER_ERROR"
            )


__all__ = ["MetadataService"]
