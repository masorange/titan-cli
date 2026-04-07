"""
GitHub Plugin Operations

Pure business logic functions that can be used in steps or called programmatically.
All functions here are UI-agnostic and can be unit tested independently.

Modules:
    comment_operations: Operations for PR comments and reviews
    pr_operations: Operations for pull requests
    worktree_operations: Operations for git worktree workflows
    pr_creation_operations: Operations for PR creation
    issue_operations: Operations for GitHub issues
"""

from .comment_operations import (
    build_ai_review_context,
    build_ai_review_prompt,
    find_ai_response_file,
    create_commit_message,
    reply_to_comment_batch,
    prepare_replies_for_sending,
)

from .pr_operations import (
    fetch_pr_threads,
    fetch_pr_general_comments,
)

from .worktree_operations import (
    setup_worktree,
    cleanup_worktree,
    commit_in_worktree,
)

from .pr_creation_operations import (
    determine_pr_assignees,
    add_assignee_if_missing,
)

from .issue_operations import (
    parse_comma_separated_list,
    filter_valid_labels,
    parse_assignees_and_labels,
)

from .code_review_operations import (
    ProjectInstructionFile,
    load_project_instructions,
    load_all_project_skills,
    load_project_docs,
    select_relevant_skills,
    select_files_for_review,
    extract_doc_summary,
    extract_diff_for_file,
    extract_hunk_for_line,
    extract_valid_diff_lines,
    find_line_by_snippet,
    build_review_payload,
    compute_diff_stat,
)

__all__ = [
    # Comment operations
    "build_ai_review_context",
    "build_ai_review_prompt",
    "find_ai_response_file",
    "create_commit_message",
    "reply_to_comment_batch",
    "prepare_replies_for_sending",

    # PR operations
    "fetch_pr_threads",
    "fetch_pr_general_comments",

    # Worktree operations
    "setup_worktree",
    "cleanup_worktree",
    "commit_in_worktree",

    # PR creation operations
    "determine_pr_assignees",
    "add_assignee_if_missing",

    # Issue operations
    "parse_comma_separated_list",
    "filter_valid_labels",
    "parse_assignees_and_labels",

    # Code review operations
    "ProjectInstructionFile",
    "load_project_instructions",
    "load_all_project_skills",
    "load_project_docs",
    "select_relevant_skills",
    "select_files_for_review",
    "extract_doc_summary",
    "extract_diff_for_file",
    "extract_hunk_for_line",
    "extract_valid_diff_lines",
    "find_line_by_snippet",
    "build_review_payload",
    "compute_diff_stat",
]
