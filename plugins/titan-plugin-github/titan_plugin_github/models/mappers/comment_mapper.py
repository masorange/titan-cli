# plugins/titan-plugin-github/titan_plugin_github/models/mappers/comment_mapper.py
"""
Comment Mappers

Converts network models (GraphQL) to view models (UI).
"""
from ..network.graphql import GraphQLPullRequestReviewComment, GraphQLIssueComment
from ..view import UIComment
from ..formatting import format_date


def from_graphql_review_comment(
    comment: GraphQLPullRequestReviewComment,
    is_outdated: bool = False
) -> UIComment:
    """
    Convert GraphQL review comment to UI comment.

    Args:
        comment: GraphQLPullRequestReviewComment from GraphQL API
        is_outdated: Whether this comment is on outdated code

    Returns:
        UIComment ready for rendering
    """
    # Extract author name
    author_name = comment.author.login if comment.author else "Unknown"

    # For outdated comments, use originalLine because diffHunk reflects old state
    # For current comments, use line
    if is_outdated and comment.originalLine:
        line_number = comment.originalLine
    else:
        line_number = comment.line or comment.originalLine

    return UIComment(
        id=comment.databaseId,
        body=comment.body,
        author_name=author_name,
        formatted_date=format_date(comment.createdAt),
        path=comment.path,
        line=line_number,
        diff_hunk=comment.diffHunk
    )


def from_graphql_issue_comment(comment: GraphQLIssueComment) -> UIComment:
    """
    Convert GraphQL issue comment to UI comment.

    Args:
        comment: GraphQLIssueComment from GraphQL API

    Returns:
        UIComment ready for rendering
    """
    # Extract author name
    author_name = comment.author.login if comment.author else "Unknown"

    return UIComment(
        id=comment.databaseId,
        body=comment.body,
        author_name=author_name,
        formatted_date=format_date(comment.createdAt),
        path=None,
        line=None,
        diff_hunk=None
    )
