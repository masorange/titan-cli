"""Jira REST API Issue Models"""

from dataclasses import dataclass
from typing import Optional, List, Dict, Any
from .user import RESTJiraUser
from .status import RESTJiraStatus
from .issue_type import RESTJiraIssueType
from .priority import RESTJiraPriority


@dataclass
class RESTJiraComponent:
    """Jira component from REST API."""
    id: str
    name: str
    description: Optional[str] = None


@dataclass
class RESTJiraVersion:
    """Jira version from REST API."""
    id: str
    name: str
    description: Optional[str] = None
    released: bool = False
    releaseDate: Optional[str] = None


@dataclass
class RESTJiraFields:
    """
    Jira issue fields from REST API.

    Contains all the nested field data from the API response.
    """
    summary: str
    description: Optional[Any] = None  # Can be ADF (dict) or string
    status: Optional[RESTJiraStatus] = None
    issuetype: Optional[RESTJiraIssueType] = None
    assignee: Optional[RESTJiraUser] = None
    reporter: Optional[RESTJiraUser] = None
    priority: Optional[RESTJiraPriority] = None
    created: Optional[str] = None
    updated: Optional[str] = None
    labels: Optional[List[str]] = None
    components: Optional[List[RESTJiraComponent]] = None
    fixVersions: Optional[List[RESTJiraVersion]] = None
    parent: Optional[Dict[str, Any]] = None  # For subtasks
    subtasks: Optional[List[Dict[str, Any]]] = None



@dataclass
class RESTJiraIssue:
    """
    Jira issue from REST API.

    Faithful to API response structure.
    This is the top-level issue object returned by the Jira REST API.
    """
    key: str
    id: str
    fields: RESTJiraFields
    self: Optional[str] = None  # API URL
    expand: Optional[str] = None
