# plugins/titan-plugin-github/titan_plugin_github/models/network/graphql/issue_comment.py
"""
GraphQL Issue Comment Model

Faithful representation of GitHub IssueComment from GraphQL API.
"""
from dataclasses import dataclass
from typing import Dict, Any

from .user import GraphQLUser


@dataclass
class GraphQLIssueComment:
    """
    General PR/issue comment not attached to specific code from GraphQL API.

    Faithful representation of GitHub's GraphQL IssueComment object.
    These are general comments on the PR itself, not inline code review comments.
    See: https://docs.github.com/en/graphql/reference/objects#issuecomment

    Field names match GraphQL schema exactly (camelCase preserved).

    Attributes:
        databaseId: Comment database ID
        body: Comment text content
        author: User who created the comment
        createdAt: Creation timestamp (ISO 8601)
        updatedAt: Last update timestamp (ISO 8601)
    """
    databaseId: int
    body: str
    author: GraphQLUser
    createdAt: str
    updatedAt: str

    @classmethod
    def from_graphql(cls, data: Dict[str, Any]) -> 'GraphQLIssueComment':
        """
        Create GraphQLIssueComment from GraphQL response.

        Args:
            data: Comment node from GraphQL IssueComment

        Returns:
            GraphQLIssueComment instance
        """
        author_data = data.get("author", {})
        author = GraphQLUser.from_graphql(author_data)

        return cls(
            databaseId=data.get("databaseId", 0),
            body=data.get("body", ""),
            author=author,
            createdAt=data.get("createdAt", ""),
            updatedAt=data.get("updatedAt", "")
        )
