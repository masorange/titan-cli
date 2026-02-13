"""
Jira UI/View Models

View models optimized for rendering Jira data in Textual TUI widgets.
Decoupled from network/API models to keep widgets stable when API changes.

All formatting, computed fields, and presentation logic lives here.
Network models contain raw API data; view models contain UI-ready data.
"""

from dataclasses import dataclass
from typing import List, Optional


@dataclass
class UIJiraIssue:
    """
    UI model for displaying a Jira issue.

    All fields are pre-formatted and ready for widget rendering.
    Computed/derived fields are calculated once during construction.
    """
    key: str                         # "PROJ-123"
    id: str                          # Database ID
    summary: str                     # Issue title
    description: str                 # Plain text (ADF converted)
    status: str                      # "To Do", "In Progress", etc.
    status_icon: str                 # "🟡" "🔵" "🟢" etc.
    status_category: str             # "To Do", "In Progress", "Done"
    issue_type: str                  # "Bug", "Story", "Task"
    issue_type_icon: str             # "🐛" "📖" "✅" etc.
    assignee: str                    # "Unassigned" or display name
    assignee_email: Optional[str]    # Email for operations
    reporter: str                    # Display name
    priority: str                    # "High", "Medium", "Low"
    priority_icon: str               # "🔴" "🟡" "🟢" etc.
    formatted_created_at: str        # "DD/MM/YYYY HH:MM:SS"
    formatted_updated_at: str        # "DD/MM/YYYY HH:MM:SS"
    labels: List[str]                # Just label names
    components: List[str]            # Component names
    fix_versions: List[str]          # Version names
    is_subtask: bool                 # Whether this is a subtask
    parent_key: Optional[str]        # Parent issue key if subtask
    subtask_count: int               # Number of subtasks


@dataclass
class UIJiraProject:
    """
    UI model for displaying a Jira project.

    All fields are pre-formatted and ready for widget rendering.
    """
    id: str
    key: str
    name: str
    description: str                 # "No description" if empty
    project_type: str                # "software", "business", etc.
    lead_name: str                   # "Unknown" if no lead
    issue_types: List[str]           # Just type names


@dataclass
class UIJiraComment:
    """
    UI model for displaying a Jira comment.

    Optimized for rendering - contains only what widgets need, with pre-formatted data.
    """
    id: str
    author_name: str
    author_email: Optional[str]
    body: str                        # Plain text (ADF converted)
    formatted_created_at: str        # "DD/MM/YYYY HH:MM:SS"
    formatted_updated_at: Optional[str]  # "DD/MM/YYYY HH:MM:SS" or None


@dataclass
class UIJiraTransition:
    """
    UI model for displaying a Jira transition.

    Optimized for rendering transition options in the TUI.
    """
    id: str
    name: str                        # "Start Progress", "Resolve Issue"
    to_status: str                   # Target status name
    to_status_icon: str              # Icon for target status


__all__ = [
    "UIJiraIssue",
    "UIJiraProject",
    "UIJiraComment",
    "UIJiraTransition",
]
