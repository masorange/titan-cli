# plugins/titan-plugin-github/titan_plugin_github/models/network/rest/issue.py
"""
REST API Issue Model

Faithful representation of GitHub issue from REST API.
"""
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any

from .user import RESTUser


@dataclass
class RESTIssue:
    """
    GitHub Issue from REST API.

    Faithful to `gh issue view --json` output.
    Field names match gh CLI JSON response (camelCase preserved).

    Attributes:
        number: Issue number
        title: Issue title
        body: Issue description
        state: Issue state (OPEN, CLOSED)
        author: Issue author
        labels: List of label objects with 'name' field
        createdAt: Creation timestamp (ISO 8601, camelCase as in API)
        updatedAt: Last update timestamp (ISO 8601, camelCase as in API)
    """
    number: int
    title: str
    body: str
    state: str
    author: RESTUser
    labels: List[Dict[str, Any]] = field(default_factory=list)  # Raw label objects
    createdAt: Optional[str] = None  # Keep camelCase from API
    updatedAt: Optional[str] = None  # Keep camelCase from API

    @classmethod
    def from_json(cls, data: Dict[str, Any]) -> 'RESTIssue':
        """
        Create RESTIssue from gh CLI JSON response.

        Args:
            data: Issue data from `gh issue view --json`

        Returns:
            RESTIssue instance
        """
        author_data = data.get("author", {})
        author = RESTUser.from_json(author_data)

        return cls(
            number=data.get("number", 0),
            title=data.get("title", ""),
            body=data.get("body", ""),
            state=data.get("state", "OPEN"),
            author=author,
            labels=data.get("labels", []),  # Keep raw label objects
            createdAt=data.get("createdAt"),
            updatedAt=data.get("updatedAt"),
        )
