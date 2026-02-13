"""Jira REST API Project Model"""

from dataclasses import dataclass
from typing import Optional, List
from .user import NetworkJiraUser
from .issue_type import NetworkJiraIssueType


@dataclass
class NetworkJiraProject:
    """
    Jira project from REST API.

    Faithful to API response structure.
    """
    id: str
    key: str
    name: str
    description: Optional[str] = None
    projectTypeKey: Optional[str] = None
    lead: Optional[NetworkJiraUser] = None
    issueTypes: Optional[List[NetworkJiraIssueType]] = None
    self: Optional[str] = None  # API URL
