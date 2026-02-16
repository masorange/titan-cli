# plugins/titan-plugin-github/titan_plugin_github/models/network/rest/pull_request.py
"""
REST API Pull Request Model

Faithful representation of GitHub PR from REST API (gh CLI).
"""
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any

from .user import NetworkUser
from .review import NetworkReview


@dataclass
class NetworkPullRequest:
    """
    GitHub Pull Request from REST API.

    Faithful to `gh pr view --json` output.
    Field names match gh CLI JSON response exactly (camelCase preserved).

    No transformations or computed fields - just raw API data.

    Attributes:
        number: PR number
        title: PR title
        body: PR description
        state: PR state (OPEN, CLOSED, MERGED)
        author: PR author
        baseRefName: Base branch name (camelCase as in API)
        headRefName: Head branch name (camelCase as in API)
        additions: Lines added
        deletions: Lines deleted
        changedFiles: Number of files changed (camelCase as in API)
        mergeable: Mergeable status string (MERGEABLE, CONFLICTING, UNKNOWN)
        isDraft: Draft status (camelCase as in API)
        createdAt: Creation timestamp (ISO 8601, camelCase as in API)
        updatedAt: Last update timestamp (ISO 8601, camelCase as in API)
        mergedAt: Merge timestamp if merged (ISO 8601, camelCase as in API)
        reviews: List of reviews
        labels: List of label objects with 'name' field
    """
    number: int
    title: str
    body: str
    state: str
    author: NetworkUser
    baseRefName: str  # Keep camelCase from API
    headRefName: str  # Keep camelCase from API
    additions: int = 0
    deletions: int = 0
    changedFiles: int = 0  # Keep camelCase from API
    mergeable: str = "UNKNOWN"  # String: MERGEABLE | CONFLICTING | UNKNOWN
    isDraft: bool = False  # Keep camelCase from API
    createdAt: Optional[str] = None  # Keep camelCase from API
    updatedAt: Optional[str] = None  # Keep camelCase from API
    mergedAt: Optional[str] = None  # Keep camelCase from API
    reviews: List[NetworkReview] = field(default_factory=list)
    labels: List[Dict[str, Any]] = field(default_factory=list)  # Raw label objects

    @classmethod
    def from_json(cls, data: Dict[str, Any]) -> 'NetworkPullRequest':
        """
        Create NetworkPullRequest from gh CLI JSON response.

        Direct 1:1 mapping from API response, no transformations.

        Args:
            data: PR data from `gh pr view --json`

        Returns:
            NetworkPullRequest instance

        Examples:
            >>> data = json.loads(subprocess.run(["gh", "pr", "view", "123", "--json", "..."]))
            >>> pr = NetworkPullRequest.from_json(data)
        """
        # Parse author
        author_data = data.get("author", {})
        author = NetworkUser.from_json(author_data)

        # Parse reviews
        reviews_data = data.get("reviews", [])
        reviews = [NetworkReview.from_json(r) for r in reviews_data]

        return cls(
            number=data.get("number", 0),
            title=data.get("title", ""),
            body=data.get("body", ""),
            state=data.get("state", "OPEN"),
            author=author,
            baseRefName=data.get("baseRefName", ""),
            headRefName=data.get("headRefName", ""),
            additions=data.get("additions", 0),
            deletions=data.get("deletions", 0),
            changedFiles=data.get("changedFiles", 0),
            mergeable=data.get("mergeable", "UNKNOWN"),
            isDraft=data.get("isDraft", False),
            createdAt=data.get("createdAt"),
            updatedAt=data.get("updatedAt"),
            mergedAt=data.get("mergedAt"),
            reviews=reviews,
            labels=data.get("labels", [])  # Keep raw label objects
        )


@dataclass
class NetworkPRSearchResult:
    """
    Result of searching pull requests via REST API.

    Attributes:
        prs: List of pull requests
        total: Total count
    """
    prs: List[NetworkPullRequest]
    total: int

    @classmethod
    def from_json_list(cls, data: List[Dict[str, Any]]) -> 'NetworkPRSearchResult':
        """
        Create NetworkPRSearchResult from list of PR JSON objects.

        Args:
            data: List of PR dictionaries from gh CLI

        Returns:
            NetworkPRSearchResult instance
        """
        prs = [NetworkPullRequest.from_json(pr_data) for pr_data in data]
        return cls(prs=prs, total=len(prs))


@dataclass
class NetworkPRMergeResult:
    """
    Result of merging a pull request via REST API.

    Attributes:
        merged: Whether the PR was successfully merged
        sha: Commit SHA of the merge (if successful)
        message: Success or error message
    """
    merged: bool
    sha: Optional[str] = None
    message: str = ""
