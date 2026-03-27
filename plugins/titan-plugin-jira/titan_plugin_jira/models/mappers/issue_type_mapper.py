"""
Issue Type Mapper

Maps NetworkJiraIssueType (network layer) to UIJiraIssueType (view layer).
"""

from ..network.rest.issue_type import NetworkJiraIssueType
from ..view import UIJiraIssueType
from ..enums import JiraIssueType


def from_network_issue_type(network_issue_type: NetworkJiraIssueType) -> UIJiraIssueType:
    """
    Map NetworkJiraIssueType to UIJiraIssueType.

    Args:
        network_issue_type: Network model from API

    Returns:
        UIJiraIssueType optimized for rendering
    """
    icon = JiraIssueType.get_icon(network_issue_type.name)
    description = network_issue_type.description or "No description"
    label = f"{icon} {network_issue_type.name}"

    return UIJiraIssueType(
        id=network_issue_type.id,
        name=network_issue_type.name,
        description=description,
        subtask=network_issue_type.subtask,
        icon=icon,
        label=label
    )


__all__ = ["from_network_issue_type"]
