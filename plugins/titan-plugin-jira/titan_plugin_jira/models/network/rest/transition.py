"""Jira REST API Transition Model"""

from dataclasses import dataclass
from typing import Optional
from .status import NetworkJiraStatus


@dataclass
class NetworkJiraTransition:
    """
    Jira transition from REST API.

    Faithful to API response structure.
    """
    id: str
    name: str
    to: Optional[NetworkJiraStatus] = None  # Target status
    hasScreen: bool = False
