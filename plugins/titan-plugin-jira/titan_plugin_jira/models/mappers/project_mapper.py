"""
Project Mapper

Converts Jira REST API project models to UI view models.
"""

from ..network.rest import RESTJiraProject
from ..view import UIJiraProject


def from_rest_project(project: RESTJiraProject) -> UIJiraProject:
    """
    Convert REST Jira project to UI project.

    Args:
        project: RESTJiraProject from REST API

    Returns:
        UIJiraProject ready for rendering

    Example:
        >>> from ..network.rest import RESTJiraProject
        >>> rest_project = RESTJiraProject(id="1", key="PROJ", name="Project")
        >>> ui_project = from_rest_project(rest_project)
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
