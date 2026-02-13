"""Jira REST API Priority Model"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class RESTJiraPriority:
    """
    Jira priority from REST API.

    Faithful to API response structure.
    """
    id: str
    name: str
    iconUrl: Optional[str] = None
