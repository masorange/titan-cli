"""
Pydantic models for the code review system.

The new-findings flow: a deterministic manifest and comments index around one free-form
review session, whose findings are deduplicated, anchored and approved by the user.
"""

from typing import Optional

from pydantic import BaseModel, Field

from .review_enums import (
    FileChangeStatus,
    FindingSeverity,
    ReviewActionSource,
    ReviewActionType,
    ThreadDecisionType,
    ThreadSeverity,
)

class ChangedFileEntry(BaseModel):
    """Single file changed in the PR with cheap deterministic signals."""

    path: str = Field(..., description="File path in repo")
    previous_path: Optional[str] = Field(default=None, description="Path before a rename, if renamed")
    status: FileChangeStatus = Field(..., description="Normalized change type")
    additions: int = Field(default=0, description="Lines added")
    deletions: int = Field(default=0, description="Lines deleted")
    is_test: bool = Field(default=False, description="Whether file is a test")
    size_lines: int = Field(default=0, description="Current file size in lines if known")
    is_docs: bool = Field(default=False, description="Documentation-like file")
    is_generated: bool = Field(default=False, description="Generated or vendored file")
    is_config: bool = Field(default=False, description="Configuration file")
    is_lockfile: bool = Field(default=False, description="Dependency lockfile")
    is_static_resource: bool = Field(default=False, description="Image, font or translatable text")
    is_rename_only: bool = Field(default=False, description="Renamed without meaningful edits")

    @property
    def total_changes(self) -> int:
        return self.additions + self.deletions

class PullRequestManifest(BaseModel):
    """Basic PR metadata."""

    number: int = Field(..., description="PR number")
    title: str = Field(..., description="PR title")
    base: str = Field(..., description="Base branch")
    head: str = Field(..., description="Head branch")
    author: str = Field(..., description="PR author login")
    description: str = Field(..., description="PR description/body")

class ChangeManifest(BaseModel):
    """Cheap deterministic context extracted from the PR."""

    pr: PullRequestManifest = Field(..., description="PR metadata")
    files: list[ChangedFileEntry] = Field(..., description="Changed files with cheap signals")
    total_additions: int = Field(..., description="Total lines added across all files")
    total_deletions: int = Field(..., description="Total lines deleted across all files")

    def summary(self) -> str:
        return (
            f"PR #{self.pr.number}: {len(self.files)} files changed "
            f"(+{self.total_additions}/-{self.total_deletions})"
        )

class ExistingCommentIndexEntry(BaseModel):
    """Compact dedupe-oriented view of an existing PR comment."""

    comment_id: int = Field(..., description="GitHub comment ID")
    thread_id: str = Field(..., description="Thread ID or general_N")
    is_resolved: bool = Field(..., description="Whether thread is resolved")
    path: Optional[str] = Field(default=None, description="File path")
    line: Optional[int] = Field(default=None, description="Target line")
    title: str = Field(..., description="Short comment title/body preview")
    body: str = Field(default="", description="The comment's text, capped; what dedupe compares against")
    author: str = Field(..., description="Comment author login")
    # A scanner or linter (Wiz, Danger...) rather than a person. Its text is boilerplate
    # about a line, so it is only matched on the very line it anchors to.
    is_bot: bool = False
    has_author_reply: bool = False
    last_reply_author: Optional[str] = None
    reply_count: int = 0
    is_adjudicated: bool = False

class CommentThreadSummary(BaseModel):
    """Compressed representation of a review thread for prompt context."""

    thread_id: str
    path: Optional[str] = None
    line: Optional[int] = None
    is_resolved: bool = False
    has_author_reply: bool = False
    last_reply_author: Optional[str] = None
    is_adjudicated: bool = False
    main_issue: str = Field(default="", description="Initial issue raised in the thread")
    latest_state: str = Field(default="", description="Latest visible response or status")
    reply_count: int = 0

class Finding(BaseModel):
    """Single problem found by AI in targeted code review."""

    severity: FindingSeverity
    category: str
    path: str
    line: Optional[int] = None
    title: str
    why: str
    evidence: str
    snippet: Optional[str] = None
    suggested_comment: str

class ThreadDecision(BaseModel):
    """AI decision on what to do with an existing review thread."""

    thread_id: str
    decision: ThreadDecisionType
    reasoning: str
    suggested_reply: Optional[str] = None
    category: Optional[str] = None
    severity: ThreadSeverity = ThreadSeverity.NONE

class ThreadReviewCandidate(BaseModel):
    """Thread selected for AI analysis in thread-resolution workflow."""

    thread_id: str
    path: Optional[str] = None
    line: Optional[int] = None
    main_comment_body: str
    main_comment_author: str
    replies_count: int = 0
    last_reply_author: Optional[str] = None
    last_reply_body: Optional[str] = None
    is_outdated: bool = False

class ReferencedCommitContext(BaseModel):
    """Remote commit context referenced from a review-thread reply."""

    sha: str
    abbreviated_sha: str
    message: str = ""
    changed_files: list[str] = Field(default_factory=list)
    patch_excerpt: Optional[str] = None

class ThreadReviewContext(BaseModel):
    """Enriched context for AI to decide what to do with a thread."""

    thread_id: str
    comment_id: int
    path: Optional[str] = None
    line: Optional[int] = None
    main_comment_body: str
    main_comment_author: str
    all_replies: list[dict] = Field(default_factory=list)
    current_code_hunk: Optional[str] = None
    referenced_commits: list[ReferencedCommitContext] = Field(default_factory=list)
    is_outdated: bool = False

class ReviewActionProposal(BaseModel):
    """Unified action ready for user review and GitHub submission."""

    action_type: ReviewActionType
    source: ReviewActionSource
    path: Optional[str] = None
    line: Optional[int] = None
    original_line: Optional[int] = None
    resolved_line: Optional[int] = None
    resolution_source: Optional[str] = None
    thread_id: Optional[str] = None
    comment_id: Optional[int] = None
    title: str
    body: str
    reasoning: str
    category: Optional[str] = None
    severity: Optional[FindingSeverity | ThreadSeverity] = None
    anchor_snippet: Optional[str] = None
    evidence: Optional[str] = None
    anchor_confidence: Optional[str] = None
    inline_reason: Optional[str] = None
    why_inline_allowed: Optional[str] = None
    is_inline_safe_for_github: bool = False
    file_status: Optional[str] = None
    is_test_file: bool = False
    related_existing_comment_ids: list[int] = Field(default_factory=list)

__all__ = [
    "ChangedFileEntry",
    "PullRequestManifest",
    "ChangeManifest",
    "ExistingCommentIndexEntry",
    "CommentThreadSummary",
    "Finding",
    "ThreadDecision",
    "ThreadReviewCandidate",
    "ThreadReviewContext",
    "ReviewActionProposal",
]
