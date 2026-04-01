"""
StrEnum definitions for the code review system.

Shared vocabulary used by review_models.py and validators.py.
"""

from enum import StrEnum


class ChecklistCategory(StrEnum):
    """Review checklist categories offered to AI during review planning."""
    FUNCTIONAL_CORRECTNESS = "functional_correctness"
    ERROR_HANDLING = "error_handling"
    TEST_COVERAGE = "test_coverage"
    SECURITY = "security"
    PERFORMANCE = "performance"
    CODE_STYLE = "code_style"
    DOCUMENTATION = "documentation"
    API_CONTRACT = "api_contract"
    CONCURRENCY = "concurrency"
    DATA_VALIDATION = "data_validation"


class FileTypeIndicator(StrEnum):
    """
    File path indicators that justify full_file read mode even on large files.

    If any of these strings appears in the file path, the validator allows
    full_file mode regardless of file size.
    """
    ADAPTER = "adapter"
    PARSER = "parser"
    WORKFLOW_STEP = "workflow_step"
    BUILDER = "builder"
    SERIALIZER = "serializer"
    DESERIALIZER = "deserializer"
    TRANSFORMER = "transformer"


class ContextRequestType(StrEnum):
    """Supported extra-context requests for targeted review."""

    RELATED_TESTS = "related_tests"
    RELATED_CONTEXT = "related_context"


class FileReviewPriority(StrEnum):
    """Relative priority assigned to a file during review planning."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class FileReadMode(StrEnum):
    """How much code to load for a file during targeted review."""

    HUNKS_ONLY = "hunks_only"
    EXPANDED_HUNKS = "expanded_hunks"
    FULL_FILE = "full_file"


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
