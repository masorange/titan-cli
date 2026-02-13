"""
Project Mapper

Converts Jira REST API project models to UI view models.
"""

from ..network.rest import NetworkJiraProject
from ..view import UIJiraProject


def from_network_project(project: NetworkJiraProject) -> UIJiraProject:
    """
    Convert REST Jira project to UI project.

    Args:
        project: NetworkJiraProject from REST API

    Returns:
        UIJiraProject ready for rendering

    Example:
        >>> from ..network.rest import NetworkJiraProject
        >>> rest_project = NetworkJiraProject(id="1", key="PROJ", name="Project")
        >>> ui_project = from_network_project(rest_project)
        >>> ui_project.description
        'No description'
    """
    lead_name = "Unknown"
    if project.lead:
        lead_name = project.lead.displayName

    issue_type_names = []
    if project.issueTypes:
        issue_type_names = [it.name for it in project.issueTypes]

    return UIJiraProject(
        id=project.id,
        key=project.key,
        name=project.name,
        description=project.description or "No description",
        project_type=project.projectTypeKey or "Unknown",
        lead_name=lead_name,
        issue_types=issue_type_names,
    )
