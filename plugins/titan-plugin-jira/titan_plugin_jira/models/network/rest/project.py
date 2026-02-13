"""Jira REST API Project Model"""

from dataclasses import dataclass
from typing import Optional, List
from .user import RESTJiraUser
from .issue_type import RESTJiraIssueType


@dataclass
class RESTJiraProject:
    """
    Jira project from REST API.

    Faithful to API response structure.
    """
    id: str
    key: str
    name: str
    description: Optional[str] = None
    projectTypeKey: Optional[str] = None
    lead: Optional[RESTJiraUser] = None
    issueTypes: Optional[List[RESTJiraIssueType]] = None
    self: Optional[str] = None  # API URL
