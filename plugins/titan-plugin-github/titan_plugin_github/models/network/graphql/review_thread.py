# plugins/titan-plugin-github/titan_plugin_github/models/network/graphql/review_thread.py
"""
GraphQL Review Thread Model

Faithful representation of GitHub PullRequestReviewThread from GraphQL API.
"""
from dataclasses import dataclass
from typing import List, Optional, Dict, Any

from .review_comment import GraphQLPullRequestReviewComment


@dataclass
class GraphQLPullRequestReviewThread:
    """
    Review thread containing a main comment and its replies from GraphQL API.

    Faithful representation of GitHub's GraphQL PullRequestReviewThread object.
    See: https://docs.github.com/en/graphql/reference/objects#pullrequestreviewthread

    Field names match GraphQL schema exactly (camelCase preserved).

    Attributes:
        id: Thread node ID (for resolving/unresolving)
        isResolved: Whether the thread has been marked as resolved
        isOutdated: Whether the code has changed since this comment was made
        path: File path where the thread is located
        comments: Connection containing comment nodes
    """
    id: str
    isResolved: bool
    isOutdated: bool
    path: Optional[str]
    comments: List[GraphQLPullRequestReviewComment]

    @classmethod
    def from_graphql(cls, data: Dict[str, Any]) -> 'GraphQLPullRequestReviewThread':
        """
        Create GraphQLPullRequestReviewThread from GraphQL response.

        Args:
            data: Thread node from GraphQL PullRequestReviewThread

        Returns:
            GraphQLPullRequestReviewThread instance
        """
        thread_id = data.get("id", "")
        is_resolved = data.get("isResolved", False)
        is_outdated = data.get("isOutdated", False)
        path = data.get("path")

        # Extract comments from connection
        comment_nodes = data.get("comments", {}).get("nodes", [])
        comments = [
            GraphQLPullRequestReviewComment.from_graphql(node)
            for node in comment_nodes
        ]

        return cls(
            id=thread_id,
            isResolved=is_resolved,
            isOutdated=is_outdated,
            path=path,
            comments=comments
        )
