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

from .plugin_docs_operations import (
    OFFICIAL_PLUGIN_REFS,
    build_all_plugin_inventories,
    build_plugin_inventory,
    extract_docstring_summary,
    inventory_output_path,
    parse_docstring_sections,
    render_plugin_inline_step_contracts_markdown,
    render_plugin_step_reference_markdown,
    step_reference_output_path,
    update_plugin_workflow_steps_pages,
    validate_generated_inventories,
    validate_generated_step_references,
    validate_workflow_steps_pages,
    write_plugin_inventories,
    write_plugin_step_references,
    workflow_steps_page_path,
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

    # Plugin docs operations
    "OFFICIAL_PLUGIN_REFS",
    "build_all_plugin_inventories",
    "build_plugin_inventory",
    "extract_docstring_summary",
    "inventory_output_path",
    "parse_docstring_sections",
    "render_plugin_inline_step_contracts_markdown",
    "render_plugin_step_reference_markdown",
    "step_reference_output_path",
    "update_plugin_workflow_steps_pages",
    "validate_generated_inventories",
    "validate_generated_step_references",
    "validate_workflow_steps_pages",
    "write_plugin_inventories",
    "write_plugin_step_references",
    "workflow_steps_page_path",
]
