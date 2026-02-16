"""
Issue Service

Handles issue-related operations.
Network → NetworkModel → UIModel → ClientResult
"""

from typing import List, Optional

from titan_cli.core.result import ClientResult, ClientSuccess, ClientError

from ..network import JiraNetwork
from ...models import (
    NetworkJiraIssue,
    NetworkJiraFields,
    NetworkJiraUser,
    NetworkJiraStatus,
    NetworkJiraStatusCategory,
    NetworkJiraIssueType,
    NetworkJiraPriority,
    UIJiraIssue,
    from_network_issue,
)
from ...models.network.rest.issue import NetworkJiraComponent, NetworkJiraVersion
from ...exceptions import JiraAPIError


class IssueService:
    """
    Service for Jira issue operations.

    PRIVATE - only used by JiraClient.
    Handles: get, search, create, update issues.
    """

    def __init__(self, network: JiraNetwork):
        """
        Initialize issue service.

        Args:
            network: JiraNetwork instance for HTTP operations
        """
        self.network = network

    def get_issue(
        self,
        key: str,
        expand: Optional[List[str]] = None
    ) -> ClientResult[UIJiraIssue]:
        """
        Get issue by key.

        Args:
            key: Issue key (e.g., "PROJ-123")
            expand: Optional fields to expand

        Returns:
            ClientResult[UIJiraIssue]
        """
        try:
            # 1. Network call
            params = {}
            if expand:
                params["expand"] = ",".join(expand)

            data = self.network.make_request("GET", f"issue/{key}", params=params)

            # 2. Parse to Network model
            network_issue = self._parse_network_issue(data)

            # 3. Map to UI model (pass raw data for custom fields access)
            ui_issue = from_network_issue(network_issue, raw=data)

            # 4. Wrap in Result
            return ClientSuccess(
                data=ui_issue,
                message=f"Issue {key} retrieved successfully"
            )

        except JiraAPIError as e:
            error_code = "ISSUE_NOT_FOUND" if e.status_code == 404 else "API_ERROR"
            return ClientError(
                error_message=str(e),
                error_code=error_code,
                details={"status_code": e.status_code} if e.status_code else None
            )

    def search_issues(
        self,
        jql: str,
        max_results: int = 50,
        fields: Optional[List[str]] = None
    ) -> ClientResult[List[UIJiraIssue]]:
        """
        Search issues using JQL.

        Args:
            jql: JQL query string
            max_results: Maximum number of results
            fields: List of fields to return

        Returns:
            ClientResult[List[UIJiraIssue]]
        """
        try:
            # 1. Network call
            payload = {
                "jql": jql,
                "maxResults": max_results,
                "fields": fields or ["summary", "status", "assignee", "priority", "created", "updated"]
            }

            data = self.network.make_request("POST", "search", json=payload)

            # 2. Parse and map each issue
            ui_issues = []
            for issue_data in data.get("issues", []):
                network_issue = self._parse_network_issue(issue_data)
                # Pass raw data to mapper for custom fields access
                ui_issue = from_network_issue(network_issue, raw=issue_data)
                ui_issues.append(ui_issue)

            # 3. Wrap in Result
            return ClientSuccess(
                data=ui_issues,
                message=f"Found {len(ui_issues)} issues"
            )

        except JiraAPIError as e:
            return ClientError(
                error_message=str(e),
                error_code="SEARCH_ERROR"
            )

    def create_issue(
        self,
        project_key: str,
        issue_type_id: str,
        summary: str,
        description: Optional[str] = None,
        assignee: Optional[str] = None,
        labels: Optional[List[str]] = None,
        priority: Optional[str] = None
    ) -> ClientResult[UIJiraIssue]:
        """
        Create new issue.

        Args:
            project_key: Project key
            issue_type_id: Issue type ID
            summary: Issue summary/title
            description: Issue description
            assignee: Assignee username or email
            labels: List of labels
            priority: Priority name

        Returns:
            ClientResult[UIJiraIssue]
        """
        try:
            # 1. Build payload
            payload = {
                "fields": {
                    "project": {"key": project_key},
                    "summary": summary,
                    "issuetype": {"id": issue_type_id}
                }
            }

            # Add description if provided
            if description:
                payload["fields"]["description"] = {
                    "type": "doc",
                    "version": 1,
                    "content": [{
                        "type": "paragraph",
                        "content": [{"type": "text", "text": description}]
                    }]
                }

            # Add optional fields
            if assignee:
                payload["fields"]["assignee"] = {"name": assignee}
            if labels:
                payload["fields"]["labels"] = labels
            if priority:
                payload["fields"]["priority"] = {"name": priority}

            # 2. Network call
            data = self.network.make_request("POST", "issue", json=payload)

            # 3. Get the created issue
            issue_key = data["key"]
            return self.get_issue(issue_key)

        except JiraAPIError as e:
            return ClientError(
                error_message=str(e),
                error_code="CREATE_ISSUE_ERROR"
            )

    def create_subtask(
        self,
        parent_key: str,
        project_key: str,
        subtask_type_id: str,
        summary: str,
        description: Optional[str] = None
    ) -> ClientResult[UIJiraIssue]:
        """
        Create subtask under parent issue.

        Args:
            parent_key: Parent issue key
            project_key: Project key
            subtask_type_id: Subtask issue type ID
            summary: Subtask summary
            description: Subtask description

        Returns:
            ClientResult[UIJiraIssue]
        """
        try:
            # 1. Build payload
            payload = {
                "fields": {
                    "project": {"key": project_key},
                    "parent": {"key": parent_key},
                    "summary": summary,
                    "issuetype": {"id": subtask_type_id}
                }
            }

            if description:
                payload["fields"]["description"] = {
                    "type": "doc",
                    "version": 1,
                    "content": [{
                        "type": "paragraph",
                        "content": [{"type": "text", "text": description}]
                    }]
                }

            # 2. Network call
            data = self.network.make_request("POST", "issue", json=payload)

            # 3. Get the created subtask
            issue_key = data["key"]
            return self.get_issue(issue_key)

        except JiraAPIError as e:
            return ClientError(
                error_message=str(e),
                error_code="CREATE_SUBTASK_ERROR"
            )

    # ==================== INTERNAL PARSERS ====================

    def _parse_user(self, user_data: Optional[dict]) -> Optional[NetworkJiraUser]:
        """Parse user data from API response"""
        if not user_data:
            return None

        return NetworkJiraUser(
            displayName=user_data.get("displayName", "Unknown"),
            accountId=user_data.get("accountId"),
            emailAddress=user_data.get("emailAddress"),
            avatarUrls=user_data.get("avatarUrls"),
            active=user_data.get("active", True),
        )

    def _parse_status(self, status_data: Optional[dict]) -> Optional[NetworkJiraStatus]:
        """Parse status data from API response"""
        if not status_data:
            return None

        status_category = None
        if status_data.get("statusCategory"):
            cat_data = status_data["statusCategory"]
            status_category = NetworkJiraStatusCategory(
                id=cat_data.get("id", ""),
                name=cat_data.get("name", ""),
                key=cat_data.get("key", ""),
                colorName=cat_data.get("colorName"),
            )

        return NetworkJiraStatus(
            id=status_data.get("id", ""),
            name=status_data.get("name", "Unknown"),
            description=status_data.get("description"),
            statusCategory=status_category,
        )

    def _parse_issue_type(self, issuetype_data: Optional[dict]) -> Optional[NetworkJiraIssueType]:
        """Parse issue type data from API response"""
        if not issuetype_data:
            return None

        return NetworkJiraIssueType(
            id=issuetype_data.get("id", ""),
            name=issuetype_data.get("name", "Unknown"),
            description=issuetype_data.get("description"),
            subtask=issuetype_data.get("subtask", False),
            iconUrl=issuetype_data.get("iconUrl"),
        )

    def _parse_priority(self, priority_data: Optional[dict]) -> Optional[NetworkJiraPriority]:
        """Parse priority data from API response"""
        if not priority_data:
            return None

        return NetworkJiraPriority(
            id=priority_data.get("id", ""),
            name=priority_data.get("name", "Unknown"),
            iconUrl=priority_data.get("iconUrl"),
        )

    def _parse_network_issue(self, issue_data: dict) -> NetworkJiraIssue:
        """Parse issue data from API response into Network model"""
        fields_data = issue_data.get("fields", {})

        # Parse nested objects
        status = self._parse_status(fields_data.get("status"))
        issuetype = self._parse_issue_type(fields_data.get("issuetype"))
        assignee = self._parse_user(fields_data.get("assignee"))
        reporter = self._parse_user(fields_data.get("reporter"))
        priority = self._parse_priority(fields_data.get("priority"))

        # Parse components
        components = []
        for comp_data in fields_data.get("components", []):
            components.append(NetworkJiraComponent(
                id=comp_data.get("id", ""),
                name=comp_data.get("name", ""),
                description=comp_data.get("description"),
            ))

        # Parse fix versions
        fix_versions = []
        for ver_data in fields_data.get("fixVersions", []):
            fix_versions.append(NetworkJiraVersion(
                id=ver_data.get("id", ""),
                name=ver_data.get("name", ""),
                description=ver_data.get("description"),
                released=ver_data.get("released", False),
                releaseDate=ver_data.get("releaseDate"),
            ))

        # Build fields object
        fields = NetworkJiraFields(
            summary=fields_data.get("summary", ""),
            description=fields_data.get("description"),  # Keep as-is (ADF or string)
            status=status,
            issuetype=issuetype,
            assignee=assignee,
            reporter=reporter,
            priority=priority,
            created=fields_data.get("created"),
            updated=fields_data.get("updated"),
            labels=fields_data.get("labels", []),
            components=components if components else None,
            fixVersions=fix_versions if fix_versions else None,
            parent=fields_data.get("parent"),
            subtasks=fields_data.get("subtasks"),
        )

        # Build issue object
        return NetworkJiraIssue(
            key=issue_data["key"],
            id=issue_data["id"],
            fields=fields,
            self=issue_data.get("self"),
            expand=issue_data.get("expand"),
        )


__all__ = ["IssueService"]
