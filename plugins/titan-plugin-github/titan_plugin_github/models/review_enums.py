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
