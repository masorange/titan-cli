"""
Comment Service

Handles comment-related operations.
Network → NetworkModel → UIModel → ClientResult
"""

from typing import List

from titan_cli.core.result import ClientResult, ClientSuccess, ClientError

from ..network import JiraNetwork
from ...models import (
    NetworkJiraComment,
    NetworkJiraUser,
    UIJiraComment,
    from_network_comment,
)
from ...exceptions import JiraAPIError


class CommentService:
    """
    Service for Jira comment operations.

    PRIVATE - only used by JiraClient.
    """

    def __init__(self, network: JiraNetwork):
        self.network = network

    def get_comments(self, issue_key: str) -> ClientResult[List[UIJiraComment]]:
        """
        Get all comments for an issue.

        Args:
            issue_key: Issue key (e.g., "PROJ-123")

        Returns:
            ClientResult[List[UIJiraComment]]
        """
        try:
            # 1. Network call
            data = self.network.make_request("GET", f"issue/{issue_key}/comment")

            # 2. Parse and map each comment
            ui_comments = []
            for comment_data in data.get("comments", []):
                network_comment = self._parse_network_comment(comment_data)
                ui_comment = from_network_comment(network_comment)
                ui_comments.append(ui_comment)

            # 3. Wrap in Result
            return ClientSuccess(
                data=ui_comments,
                message=f"Retrieved {len(ui_comments)} comments"
            )

        except JiraAPIError as e:
            return ClientError(
                error_message=str(e),
                error_code="GET_COMMENTS_ERROR"
            )

    def add_comment(self, issue_key: str, body: str) -> ClientResult[UIJiraComment]:
        """
        Add comment to issue.

        Args:
            issue_key: Issue key
            body: Comment text

        Returns:
            ClientResult[UIJiraComment]
        """
        try:
            # 1. Build payload (ADF format)
            payload = {
                "body": {
                    "type": "doc",
                    "version": 1,
                    "content": [{
                        "type": "paragraph",
                        "content": [{"type": "text", "text": body}]
                    }]
                }
            }

            # 2. Network call
            data = self.network.make_request("POST", f"issue/{issue_key}/comment", json=payload)

            # 3. Parse to Network model
            network_comment = self._parse_network_comment(data)

            # 4. Map to UI model
            ui_comment = from_network_comment(network_comment)

            # 5. Wrap in Result
            return ClientSuccess(
                data=ui_comment,
                message="Comment added successfully"
            )

        except JiraAPIError as e:
            return ClientError(
                error_message=str(e),
                error_code="ADD_COMMENT_ERROR"
            )

    def _parse_network_comment(self, data: dict) -> NetworkJiraComment:
        """Parse comment data from API response"""
        # Parse author
        author = None
        if data.get("author"):
            author = NetworkJiraUser(
                displayName=data["author"].get("displayName", "Unknown"),
                accountId=data["author"].get("accountId"),
                emailAddress=data["author"].get("emailAddress"),
                avatarUrls=data["author"].get("avatarUrls"),
                active=data["author"].get("active", True),
            )

        return NetworkJiraComment(
            id=data["id"],
            author=author,
            body=data.get("body"),  # Keep as-is (ADF or string)
            created=data.get("created"),
            updated=data.get("updated"),
            self=data.get("self"),
        )


__all__ = ["CommentService"]
