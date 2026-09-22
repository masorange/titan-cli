"""Validators and deduplication logic for the code review system."""

from difflib import SequenceMatcher

from .review_models import ExistingCommentIndexEntry, Finding


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

    if existing.is_adjudicated and similarity > 0.58:
        return True

    return similarity > title_similarity_threshold


def _lines_are_close(line_a: int | None, line_b: int | None, window: int) -> bool:
    if line_a is None and line_b is None:
        return True
    if line_a is None or line_b is None:
        return False
    return abs(line_a - line_b) <= window
