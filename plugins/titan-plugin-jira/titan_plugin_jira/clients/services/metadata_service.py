"""
Metadata Service

Handles Jira metadata operations (issue types, statuses, etc.).
Network → NetworkModel → UIModel → Result
"""

from typing import List

from titan_cli.core.result import ClientResult, ClientSuccess, ClientError
from titan_cli.core.logging import log_client_operation

from ..network import JiraNetwork
from ...models.network.rest import (
    NetworkJiraIssueType,
    NetworkJiraPriority,
    NetworkJiraStatus,
    NetworkJiraStatusCategory,
    NetworkJiraUser,
    NetworkJiraVersion
)
from ...models.view import (
    UIJiraIssueType,
    UIJiraStatus,
    UIJiraUser,
    UIJiraVersion,
    UIPriority
)
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
    def get_issue_types(self, project_key: str) -> ClientResult[List[UIJiraIssueType]]:
        """
        Get issue types for a project.

        Args:
            project_key: Project key

        Returns:
            ClientResult[List[UIJiraIssueType]]
        """
        from ...models.mappers import from_network_issue_type

        try:
            # 1. Get project (includes issue types)
            project_data = self.network.make_request("GET", f"project/{project_key}")

            # 2. Parse to network models
            network_issue_types = []
            for it_data in project_data.get("issueTypes", []):
                network_issue_types.append(NetworkJiraIssueType(
                    id=it_data.get("id", ""),
                    name=it_data.get("name", ""),
                    description=it_data.get("description"),
                    subtask=it_data.get("subtask", False),
                    iconUrl=it_data.get("iconUrl"),
                ))

            # 3. Map to UI models
            ui_issue_types = [from_network_issue_type(it) for it in network_issue_types]

            # 4. Wrap in Result
            return ClientSuccess(
                data=ui_issue_types,
                message=f"Found {len(ui_issue_types)} issue types"
            )

        except JiraAPIError as e:
            return ClientError(
                error_message=f"Failed to get issue types for {project_key}: {e.message}",
                error_code="GET_ISSUE_TYPES_ERROR"
            )

    @log_client_operation()
    def list_statuses(self, project_key: str) -> ClientResult[List[UIJiraStatus]]:
        """
        List all available statuses for a project.

        Args:
            project_key: Project key

        Returns:
            ClientResult[List[UIJiraStatus]]
        """
        from ...models.mappers import from_network_status

        try:
            # 1. Network call
            data = self.network.make_request("GET", f"project/{project_key}/statuses")

            # 2. Parse to network models (extract unique statuses)
            network_statuses = []
            seen_names = set()

            for issue_type_data in data:
                for status_data in issue_type_data.get("statuses", []):
                    status_name = status_data.get("name")
                    if status_name and status_name not in seen_names:
                        status_category_data = status_data.get("statusCategory", {})
                        status_category = NetworkJiraStatusCategory(
                            id=status_category_data.get("id", ""),
                            name=status_category_data.get("name", "To Do"),
                            key=status_category_data.get("key", "new"),
                            colorName=status_category_data.get("colorName")
                        )

                        network_statuses.append(NetworkJiraStatus(
                            id=status_data.get("id", ""),
                            name=status_name,
                            description=status_data.get("description"),
                            statusCategory=status_category
                        ))
                        seen_names.add(status_name)

            # 3. Map to UI models
            ui_statuses = [from_network_status(s) for s in network_statuses]

            # 4. Wrap in Result
            return ClientSuccess(
                data=ui_statuses,
                message=f"Found {len(ui_statuses)} statuses"
            )

        except JiraAPIError as e:
            return ClientError(
                error_message=f"Failed to list statuses for {project_key}: {e.message}",
                error_code="LIST_STATUSES_ERROR"
            )

    @log_client_operation()
    def get_current_user(self) -> ClientResult[UIJiraUser]:
        """
        Get current authenticated user info.

        Returns:
            ClientResult[UIJiraUser]
        """
        from ...models.mappers import from_network_user

        try:
            # 1. Network call
            data = self.network.make_request("GET", "myself")

            # 2. Parse to network model
            network_user = NetworkJiraUser(
                displayName=data.get("displayName", "Unknown"),
                accountId=data.get("accountId"),
                emailAddress=data.get("emailAddress"),
                avatarUrls=data.get("avatarUrls"),
                active=data.get("active", True)
            )

            # 3. Map to UI model
            ui_user = from_network_user(network_user)

            # 4. Wrap in Result
            return ClientSuccess(
                data=ui_user,
                message="Current user retrieved"
            )

        except JiraAPIError as e:
            return ClientError(
                error_message=f"Failed to get current user: {e.message}",
                error_code="GET_USER_ERROR"
            )

    @log_client_operation()
    def list_project_versions(self, project_key: str) -> ClientResult[List[UIJiraVersion]]:
        """
        List all versions for a project.

        Args:
            project_key: Project key

        Returns:
            ClientResult[List[UIJiraVersion]]
        """
        from ...models.mappers import from_network_version

        try:
            # 1. Get project (includes versions)
            project_data = self.network.make_request("GET", f"project/{project_key}")

            # 2. Parse to network models
            network_versions = []
            for v_data in project_data.get("versions", []):
                network_versions.append(NetworkJiraVersion(
                    id=v_data.get("id", ""),
                    name=v_data.get("name", ""),
                    description=v_data.get("description"),
                    released=v_data.get("released", False),
                    releaseDate=v_data.get("releaseDate")
                ))

            # 3. Map to UI models
            ui_versions = [from_network_version(v) for v in network_versions]

            # 4. Wrap in Result
            return ClientSuccess(
                data=ui_versions,
                message=f"Found {len(ui_versions)} versions"
            )

        except JiraAPIError as e:
            return ClientError(
                error_message=f"Failed to list versions for {project_key}: {e.message}",
                error_code="LIST_VERSIONS_ERROR"
            )

    def get_priorities(self) -> ClientResult[List[UIPriority]]:
        """
        Get all available priorities in Jira.

        Returns:
            ClientResult[List[UIPriority]]
        """
        from ...models.mappers import from_network_priority

        try:
            priorities_data = self.network.make_request("GET", "priority")

            # Parse to network models
            network_priorities = []
            for p_data in priorities_data:
                network_priorities.append(
                    NetworkJiraPriority(
                        id=p_data.get("id", ""),
                        name=p_data.get("name", ""),
                        iconUrl=p_data.get("iconUrl")
                    )
                )

            # Map to UI models
            ui_priorities = [from_network_priority(p) for p in network_priorities]

            return ClientSuccess(
                data=ui_priorities,
                message=f"Found {len(ui_priorities)} priorities"
            )

        except JiraAPIError as e:
            return ClientError(
                error_message=f"Failed to get priorities: {e.message}",
                error_code="GET_PRIORITIES_ERROR"
            )

    @log_client_operation()
    def find_subtask_issue_type(self, project_key: str) -> ClientResult[UIJiraIssueType]:
        """
        Find the first subtask issue type for a project.

        Args:
            project_key: Project key

        Returns:
            ClientResult[UIJiraIssueType]
        """
        # Delegate to get_issue_types
        issue_types_result = self.get_issue_types(project_key)

        match issue_types_result:
            case ClientSuccess(data=issue_types):
                # Find first subtask type
                subtask_type = next((it for it in issue_types if it.subtask), None)

                if not subtask_type:
                    return ClientError(
                        error_message=f"No subtask issue type found for project {project_key}",
                        error_code="SUBTASK_TYPE_NOT_FOUND"
                    )

                return ClientSuccess(
                    data=subtask_type,
                    message=f"Found subtask issue type: {subtask_type.name}"
                )
            case ClientError() as error:
                return error


__all__ = ["MetadataService"]
