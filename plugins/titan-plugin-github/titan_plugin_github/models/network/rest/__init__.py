"""
REST API Network Models

Faithful representations of GitHub REST API responses (gh CLI JSON output).
Field names preserve API conventions (camelCase).
No transformations or computed fields.
"""

from .user import RESTUser
from .review import RESTReview
from .pull_request import RESTPullRequest, RESTPRSearchResult, RESTPRMergeResult
from .issue import RESTIssue

__all__ = [
    "RESTUser",
    "RESTReview",
    "RESTPullRequest",
    "RESTPRSearchResult",
    "RESTPRMergeResult",
    "RESTIssue",
]
