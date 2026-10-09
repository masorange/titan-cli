"""Jira REST API Component Model"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class NetworkJiraComponent:
    """
    Jira project component from REST API.

    Faithful to API response structure.
    """
    id: str
    name: str
    description: Optional[str] = None
