"""
Comment Mapper

Converts Jira REST API comment models to UI view models.
"""

from ..network.rest import NetworkJiraComment
from ..view import UIJiraComment
from ..formatting import format_jira_date, extract_text_from_adf


def from_network_comment(comment: NetworkJiraComment) -> UIJiraComment:
    """
    Convert REST Jira comment to UI comment.

    Args:
        comment: NetworkJiraComment from REST API

    Returns:
        UIJiraComment ready for rendering

    Example:
        >>> from ..network.rest import NetworkJiraComment, NetworkJiraUser
        >>> author = NetworkJiraUser(displayName="Alice", emailAddress="alice@example.com")
        >>> rest_comment = NetworkJiraComment(id="1", author=author, body="Test", created="2025-01-15T10:30:45Z")
        >>> ui_comment = from_network_comment(rest_comment)
        >>> ui_comment.author_name
        'Alice'
    """
    author_name = "Unknown"
    author_email = None
    if comment.author:
        author_name = comment.author.displayName
        author_email = comment.author.emailAddress

    # Extract plain text from ADF body
    body_text = extract_text_from_adf(comment.body)

    formatted_updated = None
    if comment.updated:
        formatted_updated = format_jira_date(comment.updated)

    return UIJiraComment(
        id=comment.id,
        author_name=author_name,
        author_email=author_email,
        body=body_text or "No content",
        formatted_created_at=format_jira_date(comment.created),
        formatted_updated_at=formatted_updated,
    )
