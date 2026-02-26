"""
Titan CLI Operations

Pure business logic functions that can be used in steps or called programmatically.
All functions here are UI-agnostic and can be unit tested independently.
"""

from .ruff_operations import (
    parse_ruff_json_output,
    format_file_path,
    build_ruff_error_table_data,
    format_ruff_errors_for_ai,
)

from .pytest_operations import (
    parse_pytest_report_summary,
    build_failure_table_data,
    format_failures_for_ai,
    truncate_text,
)

from .log_operations import (
    LogEntry,
    LogSession,
    WorkflowRun,
    StepRun,
    SessionAnalysis,
    SLOW_THRESHOLD_SECONDS,
    STEP_RESULT_ICONS,
    WORKFLOW_STATUS_ICONS,
    parse_log_file,
    analyze_session,
    format_session_label,
)

__all__ = [
    # Ruff operations
    "parse_ruff_json_output",
    "format_file_path",
    "build_ruff_error_table_data",
    "format_ruff_errors_for_ai",

    # Pytest operations
    "parse_pytest_report_summary",
    "build_failure_table_data",
    "format_failures_for_ai",
    "truncate_text",

    # Log operations
    "LogEntry",
    "LogSession",
    "WorkflowRun",
    "StepRun",
    "SessionAnalysis",
    "SLOW_THRESHOLD_SECONDS",
    "STEP_RESULT_ICONS",
    "WORKFLOW_STATUS_ICONS",
    "parse_log_file",
    "analyze_session",
    "format_session_label",
]
