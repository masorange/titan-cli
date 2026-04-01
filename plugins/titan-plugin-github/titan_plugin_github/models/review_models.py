"""
Pydantic models for code review system.

Models for building cheap context, AI analysis, and review actions.
Follows two-phase architecture: cheap context → AI-directed analysis → targeted review.
"""

from typing import Literal, Optional
from pydantic import BaseModel, Field

from .review_enums import (
    ChecklistCategory,
    ContextRequestType,
    FileReadMode,
    FileReviewPriority,
    FindingSeverity,
    ReviewActionSource,
    ReviewActionType,
    ThreadDecisionType,
    ThreadSeverity,
)


class ChangedFileEntry(BaseModel):
    """Single file changed in the PR."""
    path: str = Field(..., description="File path in repo")
    status: Literal["added", "modified", "renamed", "deleted"] = Field(
        ..., description="Change type"
    )
    additions: int = Field(default=0, description="Lines added")
    deletions: int = Field(default=0, description="Lines deleted")
    is_test: bool = Field(default=False, description="Is this a test file")
    size_lines: int = Field(default=0, description="Current file size in lines")


class PullRequestManifest(BaseModel):
    """Basic PR metadata."""
    number: int = Field(..., description="PR number")
    title: str = Field(..., description="PR title")
    base: str = Field(..., description="Base branch")
    head: str = Field(..., description="Head branch")
    author: str = Field(..., description="PR author login")
    description: str = Field(..., description="PR description/body")


class ChangeManifest(BaseModel):
    """
    Cheap PR context built from metadata and git (no IA).

    This is the input to both workflows and is deterministically built
    from git data without any AI involvement.
    """
    pr: PullRequestManifest = Field(..., description="PR metadata")
    files: list[ChangedFileEntry] = Field(..., description="Changed files with stats")
    total_additions: int = Field(..., description="Total lines added across all files")
    total_deletions: int = Field(..., description="Total lines deleted across all files")

    def summary(self) -> str:
        """Human-readable summary for IA."""
        return (
            f"PR #{self.pr.number}: {len(self.files)} files changed "
            f"(+{self.total_additions}-{self.total_deletions})"
        )


class ReviewChecklistItem(BaseModel):
    """Single item in review checklist."""
    id: ChecklistCategory = Field(..., description="Unique checklist category ID")
    name: str = Field(..., description="Display name")
    description: str = Field(..., description="What this checklist item covers")
    relevant_file_patterns: list[str] = Field(
        default_factory=list,
        description="Optional glob patterns to scope this item (e.g. '*.py', '*test*')"
    )


class ExistingCommentIndexEntry(BaseModel):
    """Compacted form of existing comment for deduplication and AI context."""
    comment_id: int = Field(..., description="GitHub comment ID")
    thread_id: str = Field(..., description="Thread ID or 'general_N' for PR-level comments")
    is_resolved: bool = Field(..., description="Is the thread resolved")
    path: Optional[str] = Field(default=None, description="File path (None for PR-level comments)")
    line: Optional[int] = Field(default=None, description="Line number (None for file-level comments)")
    category: Optional[str] = Field(default=None, description="Inferred comment category/topic")
    title: str = Field(..., description="First ~50 chars of comment body")
    author: str = Field(..., description="Comment author login")

class ContextRequest(BaseModel):
    """Request for additional context beyond the diff."""
    type: ContextRequestType = Field(
        ..., description="Type of extra context needed"
    )
    for_path: str = Field(..., description="The file this extra context supports")
    reason: str = Field(default="", description="Why this context is needed")


class FileReviewPlan(BaseModel):
    """AI decision on how to read one file."""
    path: str = Field(..., description="File path (must exist in the PR)")
    priority: FileReviewPriority = Field(
        ..., description="How important this file is for the review"
    )
    read_mode: FileReadMode = Field(
        ..., description="How much of the file to read"
    )
    reasons: list[str] = Field(
        default_factory=list,
        description="Why this priority and read mode were chosen"
    )


class ReviewPlan(BaseModel):
    """
    Structured output from first IA call: "what should we read?"

    AI analyzes the cheap context and decides which parts of the PR
    deserve deep reading and what extra context is needed.
    """
    applicable_checklist: list[ChecklistCategory] = Field(
        default_factory=list,
        description="Checklist category IDs that apply to this PR"
    )
    file_plan: list[FileReviewPlan] = Field(
        default_factory=list,
        description="How to read each file (paths must exist in the PR)"
    )
    extra_context_requests: list[ContextRequest] = Field(
        default_factory=list,
        description="Additional context needed beyond the diff (max 3)"
    )


class Finding(BaseModel):
    """
    Single problem found by AI in targeted code review.

    Output from second IA call, one per problematic piece of code.
    """
    severity: FindingSeverity = Field(
        ..., description="How serious this problem is"
    )
    category: str = Field(
        ..., description="Problem category (e.g. 'error_handling', 'test_coverage')"
    )
    path: str = Field(..., description="File path where the problem is")
    line: Optional[int] = Field(
        default=None, description="Line number (None for file-level findings)"
    )
    title: str = Field(..., description="Short, actionable problem description")
    why: str = Field(..., description="Explanation of why this is a problem")
    evidence: str = Field(..., description="Code snippet or specific reference")
    suggested_comment: str = Field(
        ..., description="Ready-to-post review comment with full context"
    )


class ThreadDecision(BaseModel):
    """
    AI decision on what to do with an existing review thread.

    Output from thread resolution IA call.
    """
    thread_id: str = Field(..., description="GitHub thread ID")
    decision: ThreadDecisionType = Field(
        ..., description="Action to take on the thread"
    )
    reasoning: str = Field(..., description="Why this decision was made")
    suggested_reply: Optional[str] = Field(
        default=None, description="Reply text (only when decision='reply')"
    )
    category: Optional[str] = Field(default=None, description="Issue category")
    severity: ThreadSeverity = Field(
        default=ThreadSeverity.NONE, description="Thread severity assessment"
    )


class ThreadReviewCandidate(BaseModel):
    """Thread selected for AI analysis (open inline threads only)."""
    thread_id: str = Field(..., description="GitHub thread ID (GraphQL node ID)")
    path: Optional[str] = Field(default=None, description="File path (None for general comments)")
    line: Optional[int] = Field(default=None, description="Line number of the original comment")
    main_comment_body: str = Field(..., description="Body of the main comment")
    main_comment_author: str = Field(..., description="Author login of the main comment")
    replies_count: int = Field(default=0, description="Number of replies in the thread")
    last_reply_author: Optional[str] = Field(default=None, description="Author of the last reply")
    last_reply_body: Optional[str] = Field(default=None, description="Body of the last reply")
    is_outdated: bool = Field(default=False, description="Whether the underlying code has changed")


class ThreadReviewContext(BaseModel):
    """Enriched context for AI to decide what to do with a thread."""
    thread_id: str = Field(..., description="GitHub thread ID (GraphQL node ID)")
    comment_id: int = Field(..., description="Comment ID of main comment (for REST API)")
    path: Optional[str] = Field(default=None)
    line: Optional[int] = Field(default=None)
    main_comment_body: str = Field(..., description="Original comment body")
    main_comment_author: str = Field(..., description="Original comment author")
    all_replies: list[dict] = Field(
        default_factory=list,
        description="All replies as list of {author, body} dicts"
    )
    current_code_hunk: Optional[str] = Field(
        default=None, description="Diff hunk near the thread's line"
    )
    is_outdated: bool = Field(default=False)


# ============================================================================
# PHASE C: ACTION MODELS
# ============================================================================


class ReviewActionProposal(BaseModel):
    """
    Unified action ready for user review and GitHub submission.

    Used in both new_findings and thread_resolution workflows.
    Can represent a new inline comment, a thread reply, or a resolve action.
    """
    action_type: ReviewActionType = Field(
        ..., description="Type of GitHub action to perform"
    )
    source: ReviewActionSource = Field(
        ..., description="Which workflow produced this action"
    )
    path: Optional[str] = Field(
        default=None, description="File path (None for PR-level comments)"
    )
    line: Optional[int] = Field(default=None, description="Line number for inline comments")
    thread_id: Optional[str] = Field(
        default=None, description="Thread ID (required for resolve_thread actions)"
    )
    comment_id: Optional[int] = Field(
        default=None, description="Comment ID (required for reply_to_thread actions)"
    )
    title: str = Field(..., description="Short action description shown to the user")
    body: str = Field(..., description="Full comment text to post")
    reasoning: str = Field(..., description="Why this action is being proposed")
    category: Optional[str] = Field(default=None, description="Issue category")
    severity: Optional[str] = Field(default=None, description="Issue severity")
    related_existing_comment_ids: list[int] = Field(
        default_factory=list,
        description="Existing comment IDs this action is related to"
    )


# ============================================================================
# PHASE D: CONTEXT PACKAGE (Internal)
# ============================================================================


class FileContextEntry(BaseModel):
    """Single file's content for the review context package."""
    path: str = Field(..., description="File path")
    full_content: Optional[str] = Field(
        default=None, description="Full file content (for full_file mode)"
    )
    hunks: list[str] = Field(
        default_factory=list, description="Raw diff hunks"
    )
    expanded_hunks: list[str] = Field(
        default_factory=list, description="Diff hunks with extra surrounding context"
    )


class ReviewContextPackage(BaseModel):
    """
    Complete context for second IA call.

    Contains exact file content, applicable checklist, and compact existing comments.
    Everything the AI needs for a targeted, focused review.
    """
    files_context: dict[str, FileContextEntry] = Field(
        default_factory=dict,
        description="File content keyed by path"
    )
    checklist_applicable: list[ReviewChecklistItem] = Field(
        default_factory=list,
        description="Checklist items that apply to this PR"
    )
    existing_comments_compact: list[ExistingCommentIndexEntry] = Field(
        default_factory=list,
        description="Existing comments for deduplication context"
    )
    pr_manifest: Optional[PullRequestManifest] = Field(
        default=None, description="PR metadata for broader context"
    )
    dependency_hints: dict[str, list[str]] = Field(
        default_factory=dict,
        description="File dependency map (file → list of files it imports)"
    )
    related_files: dict[str, str] = Field(
        default_factory=dict,
        description="Related context by type (e.g. 'related_tests' → content)"
    )


__all__ = [
    "ChangedFileEntry",
    "PullRequestManifest",
    "ChangeManifest",
    "ReviewChecklistItem",
    "ExistingCommentIndexEntry",
    "ContextRequest",
    "FileReviewPlan",
    "ReviewPlan",
    "Finding",
    "ThreadDecision",
    "ThreadReviewCandidate",
    "ThreadReviewContext",
    "ReviewActionProposal",
    "FileContextEntry",
    "ReviewContextPackage",
]
