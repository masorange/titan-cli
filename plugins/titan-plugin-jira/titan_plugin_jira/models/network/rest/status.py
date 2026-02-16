"""Jira REST API Status Models"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class NetworkJiraStatusCategory:
    """Jira status category from REST API."""
    id: str
    name: str  # "To Do", "In Progress", "Done"
    key: str   # "new", "indeterminate", "done"
    colorName: Optional[str] = None


@dataclass
class NetworkJiraStatus:
    """
    Jira status from REST API.

    Faithful to API response structure.
    """
    id: str
    name: str
    description: Optional[str] = None
    statusCategory: Optional[NetworkJiraStatusCategory] = None
