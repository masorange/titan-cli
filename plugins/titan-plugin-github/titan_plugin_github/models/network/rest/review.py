# plugins/titan-plugin-github/titan_plugin_github/models/network/rest/review.py
"""
REST API Review Model

Faithful representation of GitHub PR review from REST API.
"""
from dataclasses import dataclass
from typing import Optional, Dict, Any

from .user import RESTUser


@dataclass
class RESTReview:
    """
    GitHub PR review from REST API.

    Faithful to REST API /repos/{owner}/{repo}/pulls/{number}/reviews response.
    Field names match REST API response.

    Attributes:
        id: Review ID
        user: Review author
        body: Review comment text
        state: Review state (PENDING, APPROVED, CHANGES_REQUESTED, COMMENTED)
        submitted_at: Submission timestamp (ISO 8601)
        commit_id: Commit SHA reviewed
    """
    id: int
    user: RESTUser
    body: str
    state: str  # PENDING, APPROVED, CHANGES_REQUESTED, COMMENTED
    submitted_at: Optional[str] = None
    commit_id: Optional[str] = None

    @classmethod
    def from_json(cls, data: Dict[str, Any]) -> 'RESTReview':
        """
        Create RESTReview from REST API JSON response.

        Args:
            data: Review data from GitHub REST API

        Returns:
            RESTReview instance
        """
        return cls(
            id=data.get("id", 0),
            user=RESTUser.from_json(data.get("user", {})),
            body=data.get("body", ""),
            state=data.get("state", "PENDING"),
            submitted_at=data.get("submitted_at"),
            commit_id=data.get("commit_id")
        )
