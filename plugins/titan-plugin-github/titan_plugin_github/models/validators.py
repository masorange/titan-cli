"""
Validators and deduplication logic for the code review system.

Contains:
- ReviewPlanValidator: semantic validation of AI-generated review plans
- is_duplicate: deduplication of findings vs existing comments
"""

from difflib import SequenceMatcher

from .review_enums import (
    ChecklistCategory,
    ContextRequestType,
    FileChangeStatus,
    FileReadMode,
    FileTypeIndicator,
)
from .review_models import (
    ChangeManifest,
    ReviewPlan,
    Finding,
    ExistingCommentIndexEntry,
)

MAX_EXTRA_CONTEXT_REQUESTS = 3
LARGE_FILE_THRESHOLD_LINES = 500

_ALL_CHECKLIST_IDS: frozenset[str] = frozenset(c.value for c in ChecklistCategory)
_ALL_FILE_INDICATORS: frozenset[str] = frozenset(f.value for f in FileTypeIndicator)


class ReviewPlanValidator:
    """
    Semantic validator for AI-generated ReviewPlan objects.

    Validates that the plan is consistent with the change manifest:
    - All file paths exist in the PR
    - Context requests are within allowed limits and use valid types
    - full_file mode is only used for small, new, or specially typed files
    - Checklist items are from the offered set
    """

    def __init__(
        self,
        change_manifest: ChangeManifest,
        offered_checklist_ids: frozenset[str] | None = None,
    ):
        self.manifest = change_manifest
        self.offered_checklist_ids = offered_checklist_ids or _ALL_CHECKLIST_IDS

    def validate_semantically(self, plan: ReviewPlan) -> tuple[bool, list[str]]:
        """
        Validate plan against change manifest.

        Args:
            plan: ReviewPlan from AI analysis phase

        Returns:
            Tuple of (is_valid, list_of_error_messages)
        """
        errors: list[str] = []
        manifest_paths = {f.path for f in self.manifest.files}

        self._check_file_paths(plan, manifest_paths, errors)
        self._check_context_request_count(plan, errors)
        self._check_context_request_types(plan, errors)
        self._check_checklist_items(plan, errors)
        self._check_full_file_mode(plan, errors)

        return len(errors) == 0, errors

    def _check_file_paths(
        self, plan: ReviewPlan, manifest_paths: set[str], errors: list[str]
    ) -> None:
        for file_plan in plan.file_plan:
            if file_plan.path not in manifest_paths:
                errors.append(f"Path not in PR: {file_plan.path}")

    def _check_context_request_count(self, plan: ReviewPlan, errors: list[str]) -> None:
        count = len(plan.extra_context_requests)
        if count > MAX_EXTRA_CONTEXT_REQUESTS:
            errors.append(
                f"Too many context requests: {count} > {MAX_EXTRA_CONTEXT_REQUESTS}"
            )

    def _check_context_request_types(self, plan: ReviewPlan, errors: list[str]) -> None:
        allowed = {ContextRequestType.RELATED_TESTS, ContextRequestType.RELATED_CONTEXT}
        for req in plan.extra_context_requests:
            if req.type not in allowed:
                errors.append(f"Invalid context type: {req.type}")

    def _check_checklist_items(self, plan: ReviewPlan, errors: list[str]) -> None:
        for item_id in plan.applicable_checklist:
            if item_id not in self.offered_checklist_ids:
                errors.append(f"Unknown checklist item: {item_id}")

    def _check_full_file_mode(self, plan: ReviewPlan, errors: list[str]) -> None:
        path_to_entry = {f.path: f for f in self.manifest.files}

        for fp in plan.file_plan:
            if fp.read_mode != FileReadMode.FULL_FILE:
                continue

            entry = path_to_entry.get(fp.path)
            if not entry:
                continue  # Path error already caught above

            if entry.size_lines <= LARGE_FILE_THRESHOLD_LINES:
                continue  # Small file: full_file is fine

            if entry.status in (FileChangeStatus.ADDED, FileChangeStatus.DELETED):
                continue  # New or deleted file: full_file is fine

            is_special = any(indicator in fp.path for indicator in _ALL_FILE_INDICATORS)
            if not is_special:
                errors.append(
                    f"full_file requested for large file ({entry.size_lines} lines) "
                    f"without special type indicator: {fp.path}"
                )

def is_duplicate(
    new_finding: Finding,
    existing: ExistingCommentIndexEntry,
    line_proximity_window: int = 5,
    title_similarity_threshold: float = 0.75,
) -> bool:
    """
    Check if a new finding duplicates an existing comment.

    A finding is a duplicate if it targets the same file, the same area
    (within line_proximity_window), and covers the same topic (same category
    or similar title).

    Args:
        new_finding: Finding from AI analysis
        existing: Compacted existing comment to compare against
        line_proximity_window: Max line distance to consider "close"
        title_similarity_threshold: Minimum SequenceMatcher ratio for title match

    Returns:
        True if the finding is a likely duplicate of the existing comment
    """
    if new_finding.path != existing.path:
        return False

    if not _lines_are_close(new_finding.line, existing.line, line_proximity_window):
        return False

    # Category exact match (case-insensitive)
    if new_finding.category.lower() == (existing.category or "").lower():
        return True

    # Title similarity fallback
    sim = SequenceMatcher(
        None,
        new_finding.title.lower(),
        existing.title.lower(),
    ).ratio()
    return sim > title_similarity_threshold


def _lines_are_close(
    line_a: int | None,
    line_b: int | None,
    window: int,
) -> bool:
    """Return True if both lines are within proximity window, or both are file-level."""
    if line_a is None and line_b is None:
        return True  # Both are file-level comments
    if line_a is None or line_b is None:
        return False  # One is file-level, the other inline
    return abs(line_a - line_b) <= window
