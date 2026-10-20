# plugins/titan-plugin-github/titan_plugin_github/models/network/rest/review.py
"""
REST API Review Model

Faithful representation of GitHub PR review from REST API.
"""
from dataclasses import dataclass
from typing import Optional, Dict, Any

from .user import NetworkUser


@dataclass
class NetworkReview:
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
    user: NetworkUser
    body: str
    state: str  # PENDING, APPROVED, CHANGES_REQUESTED, COMMENTED
    submitted_at: Optional[str] = None
    commit_id: Optional[str] = None

    @classmethod
    def from_gh_json(cls, data: Dict[str, Any]) -> 'NetworkReview':
        """
        Create NetworkReview from a `gh pr list --json latestReviews` entry.

        gh names the same review differently there: `author` instead of `user`,
        `submittedAt` instead of `submitted_at`, and an empty `id`.

        Args:
            data: One entry of gh's `latestReviews`

        Returns:
            NetworkReview instance
        """
        raw_id = data.get("id") or 0
        return cls(
            id=int(raw_id) if str(raw_id).isdigit() else 0,
            user=NetworkUser.from_json(data.get("author", {})),
            body=data.get("body", ""),
            state=data.get("state", "PENDING"),
            submitted_at=data.get("submittedAt"),
            commit_id=(data.get("commit") or {}).get("oid"),
        )

    @classmethod
    def from_json(cls, data: Dict[str, Any]) -> 'NetworkReview':
        """
        Create NetworkReview from REST API JSON response.

        Args:
            data: Review data from GitHub REST API

        Returns:
            NetworkReview instance
        """
        return cls(
            id=data.get("id", 0),
            user=NetworkUser.from_json(data.get("user", {})),
            body=data.get("body", ""),
            state=data.get("state", "PENDING"),
            submitted_at=data.get("submitted_at"),
            commit_id=data.get("commit_id")
        )
