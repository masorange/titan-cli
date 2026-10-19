"""Jira REST API Filter Model"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class NetworkJiraFilter:
    """
    Jira saved filter from REST API.

    Faithful to API response structure.
    """
    id: str
    name: str
    jql: str
    viewUrl: Optional[str] = None
    favourite: bool = False
