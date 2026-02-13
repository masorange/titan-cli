"""
Jira Models Package

Organized into layers:
- network.rest: Faithful REST API response models
- view: UI-optimized models with pre-formatted fields
- mappers: Pure functions converting network → view
- formatting: Shared formatting utilities
"""

# Network models (REST API)
from .network.rest import (
    RESTJiraIssue,
    RESTJiraFields,
    RESTJiraProject,
    RESTJiraComment,
    RESTJiraTransition,
    RESTJiraIssueType,
    RESTJiraUser,
    RESTJiraStatus,
    RESTJiraStatusCategory,
    RESTJiraPriority,
)

# View models (UI)
from .view import (
    UIJiraIssue,
    UIJiraProject,
    UIJiraComment,
    UIJiraTransition,
)

# Mappers (network → view)
from .mappers import (
    from_rest_issue,
    from_rest_project,
    from_rest_comment,
    from_rest_transition,
)

# Formatting utilities
from .formatting import (
    format_jira_date,
    get_status_icon,
    get_issue_type_icon,
    get_priority_icon,
    extract_text_from_adf,
    truncate_text,
)

__all__ = [
    # Network models
    "RESTJiraIssue",
    "RESTJiraFields",
    "RESTJiraProject",
    "RESTJiraComment",
    "RESTJiraTransition",
    "RESTJiraIssueType",
    "RESTJiraUser",
    "RESTJiraStatus",
    "RESTJiraStatusCategory",
    "RESTJiraPriority",
    # View models
    "UIJiraIssue",
    "UIJiraProject",
    "UIJiraComment",
    "UIJiraTransition",
    # Mappers
    "from_rest_issue",
    "from_rest_project",
    "from_rest_comment",
    "from_rest_transition",
    # Formatting
    "format_jira_date",
    "get_status_icon",
    "get_issue_type_icon",
    "get_priority_icon",
    "extract_text_from_adf",
    "truncate_text",
]
