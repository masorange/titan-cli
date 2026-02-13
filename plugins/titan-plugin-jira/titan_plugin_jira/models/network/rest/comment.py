"""Jira REST API Comment Model"""

from dataclasses import dataclass
from typing import Optional, Any
from .user import RESTJiraUser


@dataclass
class RESTJiraComment:
    """
    Jira comment from REST API.

    Faithful to API response structure.
    """
    id: str
    author: Optional[RESTJiraUser] = None
    body: Optional[Any] = None  # Can be ADF (dict) or string
    created: Optional[str] = None
    updated: Optional[str] = None
    self: Optional[str] = None  # API URL
