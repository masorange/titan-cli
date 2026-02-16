# plugins/titan-plugin-github/titan_plugin_github/models/mappers/issue_mapper.py
"""
Issue Mappers

Converts network models (REST) to view models (UI).
"""
from ..network.rest import NetworkIssue
from ..view import UIIssue
from ..formatting import format_date, get_issue_status_icon


def from_rest_issue(rest_issue: NetworkIssue) -> UIIssue:
    """
    Convert REST Issue to UI Issue.

    Args:
        rest_issue: NetworkIssue from REST API

    Returns:
        UIIssue ready for rendering
    """
    # Extract label names from label objects
    label_names = [label.get("name", "") for label in rest_issue.labels]

    return UIIssue(
        number=rest_issue.number,
        title=rest_issue.title,
        body=rest_issue.body,
        status_icon=get_issue_status_icon(rest_issue.state),
        state=rest_issue.state,
        author_name=rest_issue.author.login,
        labels=label_names,
        formatted_created_at=format_date(rest_issue.createdAt) if rest_issue.createdAt else "",
        formatted_updated_at=format_date(rest_issue.updatedAt) if rest_issue.updatedAt else "",
    )
