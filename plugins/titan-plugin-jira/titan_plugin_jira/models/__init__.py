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
    NetworkJiraIssue,
    NetworkJiraFields,
    NetworkJiraProject,
    NetworkJiraComment,
    NetworkJiraTransition,
    NetworkJiraIssueType,
    NetworkJiraUser,
    NetworkJiraStatus,
    NetworkJiraStatusCategory,
    NetworkJiraPriority,
    NetworkJiraVersion,
    NetworkJiraComponent,
    NetworkJiraFilter,
)

# View models (UI)
from .view import (
    UIJiraIssue,
    UIJiraProject,
    UIJiraComment,
    UIJiraTransition,
    UIPriority,
    UIJiraStatus,
    UIJiraUser,
    UIJiraIssueType,
    UIJiraVersion,
    UIJiraComponent,
    UIJiraFilter,
)

# Mappers (network → view)
from .mappers import (
    from_network_issue,
    from_network_project,
    from_network_comment,
    from_network_transition,
    from_network_priority,
    from_network_status,
    from_network_user,
    from_network_issue_type,
    from_network_version,
    from_network_component,
    from_network_filter,
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
    "NetworkJiraIssue",
    "NetworkJiraFields",
    "NetworkJiraProject",
    "NetworkJiraComment",
    "NetworkJiraTransition",
    "NetworkJiraIssueType",
    "NetworkJiraUser",
    "NetworkJiraStatus",
    "NetworkJiraStatusCategory",
    "NetworkJiraPriority",
    "NetworkJiraVersion",
    "NetworkJiraComponent",
    "NetworkJiraFilter",
    # View models
    "UIJiraIssue",
    "UIJiraProject",
    "UIJiraComment",
    "UIJiraTransition",
    "UIPriority",
    "UIJiraStatus",
    "UIJiraUser",
    "UIJiraIssueType",
    "UIJiraVersion",
    "UIJiraComponent",
    "UIJiraFilter",
    # Mappers
    "from_network_issue",
    "from_network_project",
    "from_network_comment",
    "from_network_transition",
    "from_network_priority",
    "from_network_status",
    "from_network_user",
    "from_network_issue_type",
    "from_network_version",
    "from_network_component",
    "from_network_filter",
    # Formatting
    "format_jira_date",
    "get_status_icon",
    "get_issue_type_icon",
    "get_priority_icon",
    "extract_text_from_adf",
    "truncate_text",
]
