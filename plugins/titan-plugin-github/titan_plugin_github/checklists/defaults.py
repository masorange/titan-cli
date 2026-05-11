"""Default checklist definitions for GitHub code review."""

from ..models.review_enums import ChecklistCategory
from ..models.review_models import ReviewChecklistItem


# Order matters: higher priority items first (functional correctness before style).
DEFAULT_REVIEW_CHECKLIST: list[ReviewChecklistItem] = [
    ReviewChecklistItem(
        id=ChecklistCategory.FUNCTIONAL_CORRECTNESS,
        name="Functional Correctness",
        description=(
            "Logic bugs, incorrect behavior, edge cases not handled, "
            "off-by-one errors, wrong conditions."
        ),
        relevant_file_patterns=[],
    ),
    ReviewChecklistItem(
        id=ChecklistCategory.ERROR_HANDLING,
        name="Error Handling",
        description=(
            "Missing try/except, unhandled exceptions, swallowed errors, "
            "no fallback on failure, error propagation issues."
        ),
        relevant_file_patterns=[],
    ),
    ReviewChecklistItem(
        id=ChecklistCategory.SEMANTIC_CORRECTNESS,
        name="Semantic Correctness",
        description=(
            "Changes that preserve execution but alter the meaning, classification, "
            "labeling, or interpretation of data, events, or outputs."
        ),
        relevant_file_patterns=[],
    ),
    ReviewChecklistItem(
        id=ChecklistCategory.STATE_CONSISTENCY,
        name="State Consistency",
        description=(
            "Changes that report success, failure, completion, or state inconsistently "
            "with what actually happened."
        ),
        relevant_file_patterns=[],
    ),
    ReviewChecklistItem(
        id=ChecklistCategory.TEST_COVERAGE,
        name="Test Coverage",
        description=(
            "Missing tests for new or changed logic, no regression tests, "
            "tests that don't actually exercise the code path."
        ),
        relevant_file_patterns=["*test*", "*spec*"],
    ),
    ReviewChecklistItem(
        id=ChecklistCategory.SECURITY,
        name="Security",
        description=(
            "SQL injection, XSS, SSRF, hardcoded secrets, unsafe deserialization, "
            "missing auth checks, exposed sensitive data."
        ),
        relevant_file_patterns=[],
    ),
    ReviewChecklistItem(
        id=ChecklistCategory.PERFORMANCE,
        name="Performance",
        description=(
            "N+1 queries, missing indexes, unbounded loops, large in-memory operations, "
            "missing caching for expensive calls."
        ),
        relevant_file_patterns=[],
    ),
    ReviewChecklistItem(
        id=ChecklistCategory.API_CONTRACT,
        name="API Contract",
        description=(
            "Breaking changes to public interfaces, missing backwards compatibility, "
            "changed serialization format, removed fields."
        ),
        relevant_file_patterns=["*.yaml", "*.json", "schema*", "models*", "api*"],
    ),
    ReviewChecklistItem(
        id=ChecklistCategory.DATA_VALIDATION,
        name="Data Validation",
        description=(
            "Missing input validation, trusting external data, no bounds checking, "
            "type coercion issues, null/None not handled."
        ),
        relevant_file_patterns=[],
    ),
    ReviewChecklistItem(
        id=ChecklistCategory.CONCURRENCY,
        name="Concurrency",
        description=(
            "Race conditions, missing locks, shared mutable state, "
            "thread-unsafe operations, async/await misuse."
        ),
        relevant_file_patterns=[],
    ),
    ReviewChecklistItem(
        id=ChecklistCategory.CODE_STYLE,
        name="Code Style & Maintainability",
        description=(
            "Overly complex logic with no explanation, magic numbers/strings, "
            "deep nesting, functions doing too many things."
        ),
        relevant_file_patterns=[],
    ),
    ReviewChecklistItem(
        id=ChecklistCategory.DOCUMENTATION,
        name="Documentation",
        description=(
            "Missing docstrings for public APIs, confusing variable names, "
            "no comments on non-obvious logic."
        ),
        relevant_file_patterns=[],
    ),
]
