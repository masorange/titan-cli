# plugins/titan-plugin-github/titan_plugin_github/models/network/graphql/review_comment.py
"""
GraphQL Review Comment Model

Faithful representation of GitHub PullRequestReviewComment from GraphQL API.
"""
from dataclasses import dataclass
from typing import Optional, Dict, Any

from .user import GraphQLUser


@dataclass
class GraphQLPullRequestReviewComment:
    """
    Individual review comment on code from GraphQL API.

    Faithful representation of GitHub's GraphQL PullRequestReviewComment object.
    See: https://docs.github.com/en/graphql/reference/objects#pullrequestreviewcomment

    Field names match GraphQL schema exactly (camelCase preserved where applicable).

    Attributes:
        databaseId: Comment database ID
        body: Comment text content
        author: User who created the comment
        createdAt: Creation timestamp (ISO 8601)
        updatedAt: Last update timestamp (ISO 8601)
        path: File path being commented on
        position: Position in the diff (None if outdated)
        line: Line number in the new version of the file (None if outdated)
        originalLine: Line number in the original version before changes
        diffHunk: Diff context snippet showing the commented code
        replyTo: Parent comment if this is a reply (for threading)
    """
    databaseId: int
    body: str
    author: GraphQLUser
    createdAt: str
    updatedAt: str
    path: Optional[str] = None
    position: Optional[int] = None
    line: Optional[int] = None
    originalLine: Optional[int] = None
    diffHunk: Optional[str] = None
    replyTo: Optional['GraphQLPullRequestReviewComment'] = None

    @classmethod
    def from_graphql(cls, data: Dict[str, Any]) -> 'GraphQLPullRequestReviewComment':
        """
        Create GraphQLPullRequestReviewComment from GraphQL response.

        Args:
            data: Comment node from GraphQL PullRequestReviewComment

        Returns:
            GraphQLPullRequestReviewComment instance
        """
        author_data = data.get("author", {})
        author = GraphQLUser.from_graphql(author_data)

        # Handle replyTo for threading
        reply_to_data = data.get("replyTo")
        reply_to = None
        if reply_to_data:
            reply_to = cls.from_graphql(reply_to_data)

        return cls(
            databaseId=data.get("databaseId", 0),
            body=data.get("body", ""),
            author=author,
            createdAt=data.get("createdAt", ""),
            updatedAt=data.get("updatedAt", ""),
            path=data.get("path"),
            position=data.get("position"),
            line=data.get("line"),
            originalLine=data.get("originalLine"),
            diffHunk=data.get("diffHunk"),
            replyTo=reply_to
        )
