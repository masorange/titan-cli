"""Jira REST API Issue Models"""

from dataclasses import dataclass
from typing import Optional, List, Dict, Any
from .user import NetworkJiraUser
from .status import NetworkJiraStatus
from .issue_type import NetworkJiraIssueType
from .priority import NetworkJiraPriority


@dataclass
class NetworkJiraComponent:
    """Jira component from REST API."""
    id: str
    name: str
    description: Optional[str] = None


@dataclass
class NetworkJiraVersion:
    """Jira version from REST API."""
    id: str
    name: str
    description: Optional[str] = None
    released: bool = False
    releaseDate: Optional[str] = None


@dataclass
class NetworkJiraFields:
    """
    Jira issue fields from REST API.

    Contains all the nested field data from the API response.
    """
    summary: str
    description: Optional[Any] = None  # Can be ADF (dict) or string
    status: Optional[NetworkJiraStatus] = None
    issuetype: Optional[NetworkJiraIssueType] = None
    assignee: Optional[NetworkJiraUser] = None
    reporter: Optional[NetworkJiraUser] = None
    priority: Optional[NetworkJiraPriority] = None
    created: Optional[str] = None
    updated: Optional[str] = None
    labels: Optional[List[str]] = None
    components: Optional[List[NetworkJiraComponent]] = None
    fixVersions: Optional[List[NetworkJiraVersion]] = None
    parent: Optional[Dict[str, Any]] = None  # For subtasks
    subtasks: Optional[List[Dict[str, Any]]] = None



@dataclass
class NetworkJiraIssue:
    """
    Jira issue from REST API.

    Faithful to API response structure.
    This is the top-level issue object returned by the Jira REST API.
    """
    key: str
    id: str
    fields: NetworkJiraFields
    self: Optional[str] = None  # API URL
    expand: Optional[str] = None
