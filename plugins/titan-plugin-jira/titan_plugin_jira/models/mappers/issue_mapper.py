"""
Issue Mapper

Converts Jira REST API issue models to UI view models.
"""

from ..network.rest import RESTJiraIssue
from ..view import UIJiraIssue
from ..formatting import (
    format_jira_date,
    get_status_icon,
    get_issue_type_icon,
    get_priority_icon,
    extract_text_from_adf,
)


def from_rest_issue(issue: RESTJiraIssue) -> UIJiraIssue:
    """
    Convert REST Jira issue to UI issue.

    Args:
        issue: RESTJiraIssue from REST API

    Returns:
        UIJiraIssue ready for rendering

    Example:
        >>> from ..network.rest import RESTJiraIssue, RESTJiraFields, RESTJiraStatus, RESTJiraStatusCategory
        >>> status = RESTJiraStatus(id="1", name="To Do", statusCategory=RESTJiraStatusCategory(id="2", name="To Do", key="new"))
        >>> fields = RESTJiraFields(summary="Test", status=status, ...)
        >>> rest_issue = RESTJiraIssue(key="PROJ-1", id="1", fields=fields)
        >>> ui_issue = from_rest_issue(rest_issue)
        >>> ui_issue.status_icon
        '🟡'
    """
    fields = issue.fields

    # Extract status info
    status_name = fields.status.name if fields.status else "Unknown"
    status_category_key = (
        fields.status.statusCategory.key if (fields.status and fields.status.statusCategory) else ""
    )
    status_category_name = (
        fields.status.statusCategory.name if (fields.status and fields.status.statusCategory) else "Unknown"
    )

    # Extract issue type info
    issue_type_name = fields.issuetype.name if fields.issuetype else "Unknown"
    is_subtask = fields.issuetype.subtask if fields.issuetype else False

    # Extract assignee info
    assignee_name = "Unassigned"
    assignee_email = None
    if fields.assignee:
        assignee_name = fields.assignee.displayName
        assignee_email = fields.assignee.emailAddress

    # Extract reporter info
    reporter_name = fields.reporter.displayName if fields.reporter else "Unknown"

    # Extract priority info
    priority_name = fields.priority.name if fields.priority else "Unknown"

    # Extract parent key (for subtasks)
    parent_key = None
    if fields.parent:
        parent_key = fields.parent.get("key")

    # Count subtasks
    subtask_count = len(fields.subtasks) if fields.subtasks else 0

    # Extract description (convert ADF to plain text)
    description = extract_text_from_adf(fields.description)

    return UIJiraIssue(
        key=issue.key,
        id=issue.id,
        summary=fields.summary,
        description=description or "No description",
        status=status_name,
        status_icon=get_status_icon(status_category_key),
        status_category=status_category_name,
        issue_type=issue_type_name,
        issue_type_icon=get_issue_type_icon(issue_type_name),
        assignee=assignee_name,
        assignee_email=assignee_email,
        reporter=reporter_name,
        priority=priority_name,
        priority_icon=get_priority_icon(priority_name),
        formatted_created_at=format_jira_date(fields.created),
        formatted_updated_at=format_jira_date(fields.updated),
        labels=fields.labels or [],
        components=[c.name for c in (fields.components or [])],
        fix_versions=[v.name for v in (fields.fixVersions or [])],
        is_subtask=is_subtask,
        parent_key=parent_key,
        subtask_count=subtask_count,
    )
