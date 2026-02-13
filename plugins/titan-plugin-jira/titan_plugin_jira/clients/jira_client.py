"""
Jira Client Facade

Public API for Jira plugin.
Delegates to internal services.
"""

from typing import List, Optional

from titan_cli.core.result import ClientResult

from .network import JiraNetwork
from .services import IssueService, ProjectService, CommentService
from ..models import UIJiraIssue, UIJiraProject, UIJiraComment


class JiraClient:
    """
    Jira Client Facade.

    Public API for the Jira plugin.
    Delegates all work to internal services.

    Examples:
        >>> client = JiraClient("https://jira.example.com", "user@example.com", "token")
        >>> result = client.get_issue("PROJ-123")
        >>> match result:
        ...     case ClientSuccess(data=issue):
        ...         print(issue.summary)
    """

    def __init__(
        self,
        base_url: str,
        email: str,
        api_token: str,
        project_key: Optional[str] = None,
        timeout: int = 30
    ):
        """
        Initialize Jira client.

        Args:
            base_url: Jira instance URL
            email: User email for authentication
            api_token: Jira API token (Personal Access Token)
            project_key: Default project key (optional)
            timeout: Request timeout in seconds
        """
        self.project_key = project_key

        # Internal dependencies (private)
        self._network = JiraNetwork(base_url, email, api_token, timeout)
        self._issue_service = IssueService(self._network)
        self._project_service = ProjectService(self._network)
        self._comment_service = CommentService(self._network)

    # ==================== ISSUE OPERATIONS ====================

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

        Examples:
            >>> result = client.get_issue("PROJ-123")
            >>> match result:
            ...     case ClientSuccess(data=issue):
            ...         print(f"{issue.status_icon} {issue.summary}")
            ...     case ClientError(error_message=err):
            ...         print(f"Error: {err}")
        """
        return self._issue_service.get_issue(key, expand)

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

        Examples:
            >>> result = client.search_issues('project=PROJ AND status="To Do"')
            >>> match result:
            ...     case ClientSuccess(data=issues):
            ...         for issue in issues:
            ...             print(issue.key, issue.summary)
        """
        return self._issue_service.search_issues(jql, max_results, fields)

    # ==================== PROJECT OPERATIONS ====================

    def get_project(self, key: Optional[str] = None) -> ClientResult[UIJiraProject]:
        """
        Get project by key.

        Args:
            key: Project key (uses default if not provided)

        Returns:
            ClientResult[UIJiraProject]
        """
        project_key = key or self.project_key
        if not project_key:
            from titan_cli.core.result import ClientError
            return ClientError(
                error_message="Project key not provided",
                error_code="MISSING_PROJECT_KEY"
            )

        return self._project_service.get_project(project_key)

    def list_projects(self) -> ClientResult[List[UIJiraProject]]:
        """
        List all accessible projects.

        Returns:
            ClientResult[List[UIJiraProject]]
        """
        return self._project_service.list_projects()

    # ==================== COMMENT OPERATIONS ====================

    def get_comments(self, issue_key: str) -> ClientResult[List[UIJiraComment]]:
        """
        Get all comments for an issue.

        Args:
            issue_key: Issue key

        Returns:
            ClientResult[List[UIJiraComment]]
        """
        return self._comment_service.get_comments(issue_key)

    def add_comment(self, issue_key: str, body: str) -> ClientResult[UIJiraComment]:
        """
        Add comment to issue.

        Args:
            issue_key: Issue key
            body: Comment text

        Returns:
            ClientResult[UIJiraComment]
        """
        return self._comment_service.add_comment(issue_key, body)


__all__ = ["JiraClient"]
