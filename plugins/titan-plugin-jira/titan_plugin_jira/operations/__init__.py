"""
Jira Plugin Operations

Pure business logic functions that can be used in steps or called programmatically.
All functions here are UI-agnostic and can be unit tested independently.

Modules:
    jql_operations: Operations for JQL query handling
    issue_formatting_operations: Operations for formatting Jira issues
"""

from .jql_operations import (
    substitute_jql_variables,
    format_jql_with_project,
    merge_query_collections,
    build_query_not_found_message,
)

from .issue_formatting_operations import (
    truncate_summary,
    format_issue_field,
    build_issue_table_row,
    get_issue_table_headers,
    build_issue_table_data,
)

from .issue_operations import (
    find_ready_to_dev_transition,
    transition_issue_to_ready_for_dev,
)

__all__ = [
    # JQL operations
    "substitute_jql_variables",
    "format_jql_with_project",
    "merge_query_collections",
    "build_query_not_found_message",
    # Issue formatting operations
    "truncate_summary",
    "format_issue_field",
    "build_issue_table_row",
    "get_issue_table_headers",
    "build_issue_table_data",
    # Issue operations
    "find_ready_to_dev_transition",
    "transition_issue_to_ready_for_dev",
]
