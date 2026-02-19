"""
Project Service

Handles project-related operations.
Network → NetworkModel → UIModel → ClientResult
"""

from typing import List

from titan_cli.core.result import ClientResult, ClientSuccess, ClientError
from titan_cli.core.logging import log_client_operation

from ..network import JiraNetwork
from ...models import (
    NetworkJiraProject,
    NetworkJiraUser,
    NetworkJiraIssueType,
    UIJiraProject,
    from_network_project,
)
from ...exceptions import JiraAPIError


class ProjectService:
    """
    Service for Jira project operations.

    PRIVATE - only used by JiraClient.
    """

    def __init__(self, network: JiraNetwork):
        self.network = network

    @log_client_operation()
    def get_project(self, key: str) -> ClientResult[UIJiraProject]:
        """
        Get project by key.

        Args:
            key: Project key (e.g., "PROJ")

        Returns:
            ClientResult[UIJiraProject]
        """
        try:
            # 1. Network call
            data = self.network.make_request("GET", f"project/{key}")

            # 2. Parse to Network model
            network_project = self._parse_network_project(data)

            # 3. Map to UI model
            ui_project = from_network_project(network_project)

            # 4. Wrap in Result
            return ClientSuccess(
                data=ui_project,
                message=f"Project {key} retrieved"
            )

        except JiraAPIError as e:
            error_code = "NOT_FOUND" if e.status_code == 404 else "API_ERROR"
            return ClientError(
                error_message=str(e),
                error_code=error_code
            )

    @log_client_operation()
    def list_projects(self) -> ClientResult[List[UIJiraProject]]:
        """
        List all accessible projects.

        Returns:
            ClientResult[List[UIJiraProject]]
        """
        try:
            # 1. Network call
            data = self.network.make_request("GET", "project")

            # 2. Parse and map each project
            ui_projects = []
            for project_data in data:
                network_project = self._parse_network_project(project_data)
                ui_project = from_network_project(network_project)
                ui_projects.append(ui_project)

            # 3. Wrap in Result
            return ClientSuccess(
                data=ui_projects,
                message=f"Found {len(ui_projects)} projects"
            )

        except JiraAPIError as e:
            return ClientError(
                error_message=str(e),
                error_code="LIST_ERROR"
            )

    def _parse_network_project(self, data: dict) -> NetworkJiraProject:
        """Parse project data from API response"""
        # Parse lead
        lead = None
        if data.get("lead"):
            lead = NetworkJiraUser(
                displayName=data["lead"].get("displayName", "Unknown"),
                accountId=data["lead"].get("accountId"),
                emailAddress=data["lead"].get("emailAddress"),
                avatarUrls=data["lead"].get("avatarUrls"),
                active=data["lead"].get("active", True),
            )

        # Parse issue types
        issue_types = []
        for it_data in data.get("issueTypes", []):
            issue_types.append(NetworkJiraIssueType(
                id=it_data.get("id", ""),
                name=it_data.get("name", ""),
                description=it_data.get("description"),
                subtask=it_data.get("subtask", False),
                iconUrl=it_data.get("iconUrl"),
            ))

        return NetworkJiraProject(
            id=data["id"],
            key=data["key"],
            name=data["name"],
            description=data.get("description"),
            projectTypeKey=data.get("projectTypeKey"),
            lead=lead,
            issueTypes=issue_types if issue_types else None,
            self=data.get("self"),
        )


__all__ = ["ProjectService"]
