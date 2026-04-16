"""Validators and deduplication logic for the code review system."""

from difflib import SequenceMatcher

from .review_enums import ChecklistCategory, ContextRequestType
from .review_models import (
    ChangeManifest,
    ExistingCommentIndexEntry,
    Finding,
    ReviewPlan,
)

MAX_EXTRA_CONTEXT_REQUESTS = 3

_ALL_CHECKLIST_IDS: frozenset[str] = frozenset(c.value for c in ChecklistCategory)


class ReviewPlanValidator:
    """Semantic validator for focused review plans."""

    def __init__(
        self,
        change_manifest: ChangeManifest,
        offered_checklist_ids: frozenset[str] | None = None,
    ):
        self.manifest = change_manifest
        self.offered_checklist_ids = offered_checklist_ids or _ALL_CHECKLIST_IDS

    def validate_semantically(self, plan: ReviewPlan) -> tuple[bool, list[str]]:
        errors: list[str] = []
        manifest_paths = {f.path for f in self.manifest.files}

        if not plan.focus_files:
            errors.append("Plan has no focus_files")

        seen_focus: set[str] = set()
        for file_plan in plan.focus_files:
            if file_plan.path not in manifest_paths:
                errors.append(f"Focus path not in PR: {file_plan.path}")
            if file_plan.path in seen_focus:
                errors.append(f"Duplicate focus file: {file_plan.path}")
            seen_focus.add(file_plan.path)

        if len(plan.extra_context_requests) > MAX_EXTRA_CONTEXT_REQUESTS:
            errors.append(
                f"Too many context requests: {len(plan.extra_context_requests)} > {MAX_EXTRA_CONTEXT_REQUESTS}"
            )

        allowed_context_types = {
            ContextRequestType.RELATED_TESTS,
            ContextRequestType.RELATED_CONTEXT,
        }
        for req in plan.extra_context_requests:
            if req.type not in allowed_context_types:
                errors.append(f"Invalid context type: {req.type}")
            if req.for_path not in manifest_paths:
                errors.append(f"Context request path not in PR: {req.for_path}")

        for item_id in plan.review_axes:
            if item_id not in self.offered_checklist_ids:
                errors.append(f"Unknown checklist item: {item_id}")

        for excluded in plan.excluded_files:
            if excluded.path not in manifest_paths:
                errors.append(f"Excluded path not in PR: {excluded.path}")
            if excluded.path in seen_focus:
                errors.append(f"Path cannot be both focused and excluded: {excluded.path}")

        return len(errors) == 0, errors


def is_duplicate(
    new_finding: Finding,
    existing: ExistingCommentIndexEntry,
    line_proximity_window: int = 5,
    title_similarity_threshold: float = 0.75,
) -> bool:
    """Return True if a finding likely duplicates an existing comment."""

    if new_finding.path != existing.path:
        return False

    if not _lines_are_close(new_finding.line, existing.line, line_proximity_window):
        return False

    similarity = SequenceMatcher(
        None,
        new_finding.title.lower(),
        existing.title.lower(),
    ).ratio()

    same_category = new_finding.category.lower() == (existing.category or "").lower()
    if same_category and not existing.is_resolved:
        return True

    if same_category and existing.is_adjudicated:
        return True

    if existing.is_adjudicated and similarity > 0.58:
        return True

    return similarity > title_similarity_threshold


def _lines_are_close(line_a: int | None, line_b: int | None, window: int) -> bool:
    if line_a is None and line_b is None:
        return True
    if line_a is None or line_b is None:
        return False
    return abs(line_a - line_b) <= window
