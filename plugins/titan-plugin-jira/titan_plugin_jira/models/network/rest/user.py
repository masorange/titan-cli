"""Jira REST API User Model"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class NetworkJiraUser:
    """
    Jira user from REST API.

    Faithful to API response structure.
    """
    displayName: str
    accountId: Optional[str] = None
    emailAddress: Optional[str] = None
    avatarUrls: Optional[dict] = None
    active: bool = True
