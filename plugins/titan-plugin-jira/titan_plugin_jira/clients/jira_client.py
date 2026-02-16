"""
Jira Client Facade

Public API for Jira plugin.
Delegates to internal services.
"""

from typing import List, Optional

from titan_cli.core.result import ClientResult, ClientError

from .network import JiraNetwork
from .services import (
    IssueService,
    ProjectService,
    CommentService,
    TransitionService,
    MetadataService,
    LinkService,
)
from ..models import UIJiraIssue, UIJiraProject, UIJiraComment, UIJiraTransition, NetworkJiraIssueType


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
        self._transition_service = TransitionService(self._network)
        self._metadata_service = MetadataService(self._network)
        self._link_service = LinkService(self._network)

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

    # ==================== TRANSITION OPERATIONS ====================

    def get_transitions(self, issue_key: str) -> ClientResult[List[UIJiraTransition]]:
        """
        Get available transitions for an issue.

        Args:
            issue_key: Issue key

        Returns:
            ClientResult[List[UIJiraTransition]]
        """
        return self._transition_service.get_transitions(issue_key)

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
            comment: Optional comment

        Returns:
            ClientResult[None]
        """
        return self._transition_service.transition_issue(issue_key, new_status, comment)

    # ==================== CREATION OPERATIONS ====================

    def create_issue(
        self,
        issue_type: str,
        summary: str,
        description: Optional[str] = None,
        project: Optional[str] = None,
        assignee: Optional[str] = None,
        labels: Optional[List[str]] = None,
        priority: Optional[str] = None
    ) -> ClientResult[UIJiraIssue]:
        """
        Create new issue.

        Args:
            issue_type: Issue type name (Bug, Story, Task, etc.)
            summary: Issue summary/title
            description: Issue description
            project: Project key (uses default if not provided)
            assignee: Assignee username or email
            labels: List of labels
            priority: Priority name

        Returns:
            ClientResult[UIJiraIssue]
        """
        project_key = project or self.project_key
        if not project_key:
            return ClientError(
                error_message="Project key not provided",
                error_code="MISSING_PROJECT_KEY"
            )

        # Get issue type ID
        issue_types_result = self._metadata_service.get_issue_types(project_key)
        if isinstance(issue_types_result, ClientError):
            return issue_types_result

        issue_type_obj = None
        for it in issue_types_result.data:
            if it.name.lower() == issue_type.lower():
                issue_type_obj = it
                break

        if not issue_type_obj:
            available = [it.name for it in issue_types_result.data]
            return ClientError(
                error_message=f"Issue type '{issue_type}' not found. Available: {', '.join(available)}",
                error_code="INVALID_ISSUE_TYPE"
            )

        return self._issue_service.create_issue(
            project_key=project_key,
            issue_type_id=issue_type_obj.id,
            summary=summary,
            description=description,
            assignee=assignee,
            labels=labels,
            priority=priority
        )

    def create_subtask(
        self,
        parent_key: str,
        summary: str,
        description: Optional[str] = None
    ) -> ClientResult[UIJiraIssue]:
        """
        Create subtask under parent issue.

        Args:
            parent_key: Parent issue key
            summary: Subtask summary
            description: Subtask description

        Returns:
            ClientResult[UIJiraIssue]
        """
        if not self.project_key:
            return ClientError(
                error_message="No default project configured",
                error_code="MISSING_PROJECT_KEY"
            )

        # Get subtask issue type
        issue_types_result = self._metadata_service.get_issue_types(self.project_key)
        if isinstance(issue_types_result, ClientError):
            return issue_types_result

        subtask_type = None
        for it in issue_types_result.data:
            if it.subtask:
                subtask_type = it
                break

        if not subtask_type:
            return ClientError(
                error_message="No subtask issue type found for project",
                error_code="NO_SUBTASK_TYPE"
            )

        return self._issue_service.create_subtask(
            parent_key=parent_key,
            project_key=self.project_key,
            subtask_type_id=subtask_type.id,
            summary=summary,
            description=description
        )

    # ==================== METADATA OPERATIONS ====================

    def get_issue_types(self, project_key: Optional[str] = None) -> ClientResult[List[NetworkJiraIssueType]]:
        """
        Get issue types for a project.

        Args:
            project_key: Project key (uses default if not provided)

        Returns:
            ClientResult[List[NetworkJiraIssueType]]
        """
        key = project_key or self.project_key
        if not key:
            return ClientError(
                error_message="Project key not provided",
                error_code="MISSING_PROJECT_KEY"
            )

        return self._metadata_service.get_issue_types(key)

    def list_statuses(self, project_key: Optional[str] = None) -> ClientResult[List[dict]]:
        """
        List all available statuses for a project.

        Args:
            project_key: Project key (uses default if not provided)

        Returns:
            ClientResult[List[dict]]
        """
        key = project_key or self.project_key
        if not key:
            return ClientError(
                error_message="Project key not provided",
                error_code="MISSING_PROJECT_KEY"
            )

        return self._metadata_service.list_statuses(key)

    def get_current_user(self) -> ClientResult[dict]:
        """
        Get current authenticated user info.

        Returns:
            ClientResult[dict]
        """
        return self._metadata_service.get_current_user()

    def list_project_versions(self, project_key: Optional[str] = None) -> ClientResult[List[dict]]:
        """
        List all versions for a project.

        Args:
            project_key: Project key (uses default if not provided)

        Returns:
            ClientResult[List[dict]]
        """
        key = project_key or self.project_key
        if not key:
            return ClientError(
                error_message="Project key not provided",
                error_code="MISSING_PROJECT_KEY"
            )

        return self._metadata_service.list_project_versions(key)

    # ==================== LINK OPERATIONS ====================

    def link_issue(
        self,
        inward_issue: str,
        outward_issue: str,
        link_type: str = "Relates"
    ) -> ClientResult[None]:
        """
        Create link between two issues.

        Args:
            inward_issue: Source issue key
            outward_issue: Target issue key
            link_type: Link type name

        Returns:
            ClientResult[None]
        """
        return self._link_service.link_issues(inward_issue, outward_issue, link_type)

    def add_remote_link(
        self,
        issue_key: str,
        url: str,
        title: str,
        relationship: str = "relates to"
    ) -> ClientResult[str]:
        """
        Add remote link (e.g., GitHub PR) to issue.

        Args:
            issue_key: Issue key
            url: URL to link
            title: Link title
            relationship: Relationship description

        Returns:
            ClientResult[str] with link ID
        """
        return self._link_service.add_remote_link(issue_key, url, title, relationship)


__all__ = ["JiraClient"]
