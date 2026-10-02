"""
StrEnum definitions for the code review system.

Shared vocabulary used by the review models and operations.
"""

from enum import StrEnum


class FileChangeStatus(StrEnum):
    """Normalized file change status used in review manifests."""

    ADDED = "added"
    MODIFIED = "modified"
    RENAMED = "renamed"
    DELETED = "deleted"


class FindingSeverity(StrEnum):
    """Severity assigned to a new finding found during review."""

    BLOCKING = "blocking"
    IMPORTANT = "important"
    NIT = "nit"


class ThreadDecisionType(StrEnum):
    """AI-selected action for an existing review thread."""

    RESOLVED = "resolved"
    INSIST = "insist"
    REPLY = "reply"
    SKIP = "skip"


class ThreadSeverity(StrEnum):
    """Severity assigned while evaluating an existing review thread."""

    IMPORTANT = "important"
    NIT = "nit"
    NONE = "none"


class ReviewActionType(StrEnum):
    """Type of GitHub review action proposed by the workflow."""

    NEW_COMMENT = "new_comment"
    REPLY_TO_THREAD = "reply_to_thread"
    RESOLVE_THREAD = "resolve_thread"


class ReviewActionSource(StrEnum):
    """Workflow source that produced a review action."""

    NEW_FINDING = "new_finding"
    THREAD_FOLLOWUP = "thread_followup"
