"""Jira REST API Version Model"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class NetworkJiraVersion:
    """
    Jira version from REST API.

    Faithful to API response structure.
    """
    id: str
    name: str
    description: Optional[str] = None
    released: bool = False
    releaseDate: Optional[str] = None
