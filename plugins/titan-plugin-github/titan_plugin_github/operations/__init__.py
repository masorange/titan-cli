"""
GitHub Plugin Operations

Pure business logic functions that can be used in steps or called programmatically.
All functions here are UI-agnostic and can be unit tested independently.

Modules:
    comment_operations: Operations for PR comments and reviews
    pr_operations: Operations for pull requests
    worktree_operations: Operations for git worktree workflows
"""

from .comment_operations import (
    build_ai_review_context,
    detect_worktree_changes,
    find_ai_response_file,
    create_commit_message,
    reply_to_comment_batch,
    auto_review_comment,
)

from .pr_operations import (
    fetch_pr_threads,
    push_and_request_review,
)

from .worktree_operations import (
    setup_worktree,
    cleanup_worktree,
    commit_in_worktree,
)

__all__ = [
    # Comment operations
    "build_ai_review_context",
    "detect_worktree_changes",
    "find_ai_response_file",
    "create_commit_message",
    "reply_to_comment_batch",
    "auto_review_comment",

    # PR operations
    "fetch_pr_threads",
    "push_and_request_review",

    # Worktree operations
    "setup_worktree",
    "cleanup_worktree",
    "commit_in_worktree",
]
