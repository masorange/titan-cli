"""
Link Service

Handles issue linking operations.
"""

from titan_cli.core.result import ClientResult, ClientSuccess, ClientError

from ..network import JiraNetwork
from ...exceptions import JiraAPIError


class LinkService:
    """
    Service for Jira link operations.

    PRIVATE - only used by JiraClient.
    """

    def __init__(self, network: JiraNetwork):
        self.network = network

    def link_issues(
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
        try:
            payload = {
                "type": {"name": link_type},
                "inwardIssue": {"key": inward_issue},
                "outwardIssue": {"key": outward_issue}
            }

            self.network.make_request("POST", "issueLink", json=payload)

            return ClientSuccess(
                data=None,
                message=f"Linked {inward_issue} to {outward_issue}"
            )

        except JiraAPIError as e:
            return ClientError(
                error_message=str(e),
                error_code="LINK_ERROR"
            )

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
        try:
            payload = {
                "object": {
                    "url": url,
                    "title": title
                },
                "relationship": relationship
            }

            data = self.network.make_request("POST", f"issue/{issue_key}/remotelink", json=payload)

            link_id = data.get("id", "")
            return ClientSuccess(
                data=link_id,
                message=f"Added remote link to {issue_key}"
            )

        except JiraAPIError as e:
            return ClientError(
                error_message=str(e),
                error_code="ADD_REMOTE_LINK_ERROR"
            )


__all__ = ["LinkService"]
