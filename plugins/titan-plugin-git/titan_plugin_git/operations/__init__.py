"""
Git Plugin Operations

Pure business logic functions that can be used in steps or called programmatically.
All functions here are UI-agnostic and can be unit tested independently.

Modules:
    commit_operations: Operations for commit message handling
    diff_operations: Operations for diff parsing and formatting
    branch_operations: Operations for branch management
    worktree_operations: Operations for inspecting and removing worktrees
    merge_operations: Operations for merging branches and resolving conflicts
"""

from .commit_operations import (
    build_ai_commit_prompt,
    normalize_commit_message,
    capitalize_commit_subject,
    validate_message_length,
    process_ai_commit_message,
)

from .diff_operations import (
    parse_diff_stat_output,
    expand_rename_path,
    get_max_filename_length,
    colorize_diff_stats,
    colorize_diff_summary,
    format_diff_stat_display,
)

from .branch_operations import (
    check_branch_exists,
    parse_checkout_targets,
    order_branches_by_use,
    filter_branches,
    merge_sources,
    push_rejected_hint,
    switching_blocked_by,
    determine_safe_checkout_target,
    should_delete_before_create,
)

from .worktree_operations import (
    main_worktree_path,
    removal_blocked_by,
    same_path,
    removable_worktrees,
)

from .merge_operations import (
    resolve_merge_source,
    build_merge_ref,
    classify_merge_result,
    has_conflict_markers,
    build_conflict_resolution_prompt,
    parse_merge_tree_conflicts,
    format_merge_summary,
)

__all__ = [
    # Commit operations
    "build_ai_commit_prompt",
    "normalize_commit_message",
    "capitalize_commit_subject",
    "validate_message_length",
    "process_ai_commit_message",

    # Diff operations
    "parse_diff_stat_output",
    "expand_rename_path",
    "get_max_filename_length",
    "colorize_diff_stats",
    "colorize_diff_summary",
    "format_diff_stat_display",

    # Branch operations
    "check_branch_exists",
    "parse_checkout_targets",
    "order_branches_by_use",
    "filter_branches",
    "merge_sources",
    "push_rejected_hint",
    "switching_blocked_by",
    "determine_safe_checkout_target",
    "should_delete_before_create",

    # Worktree operations
    "main_worktree_path",
    "removal_blocked_by",
    "same_path",
    "removable_worktrees",

    # Merge operations
    "resolve_merge_source",
    "build_merge_ref",
    "classify_merge_result",
    "has_conflict_markers",
    "build_conflict_resolution_prompt",
    "parse_merge_tree_conflicts",
    "format_merge_summary",
]
