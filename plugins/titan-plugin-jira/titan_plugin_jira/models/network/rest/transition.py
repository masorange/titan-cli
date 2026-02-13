"""Jira REST API Transition Model"""

from dataclasses import dataclass
from typing import Optional
from .status import RESTJiraStatus


@dataclass
class RESTJiraTransition:
    """
    Jira transition from REST API.

    Faithful to API response structure.
    """
    id: str
    name: str
    to: Optional[RESTJiraStatus] = None  # Target status
    hasScreen: bool = False
