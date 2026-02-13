"""Jira REST API Issue Type Model"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class RESTJiraIssueType:
    """
    Jira issue type from REST API.

    Faithful to API response structure.
    """
    id: str
    name: str
    description: Optional[str] = None
    subtask: bool = False
    iconUrl: Optional[str] = None
