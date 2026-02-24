"""
Metadata Service

Handles Jira metadata operations (issue types, statuses, etc.).
Network → NetworkModel → Result
"""

from typing import List, Dict, Any

from titan_cli.core.result import ClientResult, ClientSuccess, ClientError
from titan_cli.core.logging import log_client_operation

from ..network import JiraNetwork
from ...models import NetworkJiraIssueType
from ...models.network.rest.priority import NetworkJiraPriority
from ...exceptions import JiraAPIError


class MetadataService:
    """
    Service for Jira metadata operations.

    PRIVATE - only used by JiraClient.
    Returns Network models (no UI mapping needed for metadata).
    """

    def __init__(self, network: JiraNetwork):
        self.network = network

    @log_client_operation()
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
                error_message=f"Failed to get issue types for {project_key}: {e.message}",
                error_code="GET_ISSUE_TYPES_ERROR"
            )

    @log_client_operation()
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
                error_message=f"Failed to list statuses for {project_key}: {e.message}",
                error_code="LIST_STATUSES_ERROR"
            )

    @log_client_operation()
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
                error_message=f"Failed to get current user: {e.message}",
                error_code="GET_USER_ERROR"
            )

    @log_client_operation()
    def list_project_versions(self, project_key: str) -> ClientResult[List[Dict[str, Any]]]:
        """
        List all versions for a project.

        Args:
            project_key: Project key

        Returns:
            ClientResult[List[Dict]] with version info (id, name, description, released, releaseDate)
        """
        try:
            # Get project (includes versions)
            project_data = self.network.make_request("GET", f"project/{project_key}")

            # Extract versions
            versions = project_data.get("versions", [])

            # Parse version data
            version_list = []
            for v_data in versions:
                version_list.append({
                    "id": v_data.get("id"),
                    "name": v_data.get("name"),
                    "description": v_data.get("description"),
                    "released": v_data.get("released", False),
                    "releaseDate": v_data.get("releaseDate")
                })

            return ClientSuccess(
                data=version_list,
                message=f"Found {len(version_list)} versions"
            )

        except JiraAPIError as e:
            return ClientError(
                error_message=f"Failed to list versions for {project_key}: {e.message}",
                error_code="LIST_VERSIONS_ERROR"
            )

    def get_priorities(self) -> ClientResult[List[NetworkJiraPriority]]:
        """
        Get all available priorities in Jira.

        Returns:
            ClientResult[List[NetworkJiraPriority]]
        """
        try:
            priorities_data = self.network.make_request("GET", "priority")

            # Parse to network models
            priorities = []
            for p_data in priorities_data:
                priorities.append(
                    NetworkJiraPriority(
                        id=p_data.get("id", ""),
                        name=p_data.get("name", ""),
                        iconUrl=p_data.get("iconUrl")
                    )
                )

            return ClientSuccess(
                data=priorities,
                message=f"Found {len(priorities)} priorities"
            )

        except JiraAPIError as e:
            return ClientError(
                error_message=f"Failed to get priorities: {e.message}",
                error_code="GET_PRIORITIES_ERROR"
            )


__all__ = ["MetadataService"]
