"""Validators and deduplication logic for the code review system."""

import re
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

    # Whether the two SAY the same thing. A shared category is no longer enough on its
    # own: the existing comment's category is guessed from keywords, so "Shouldn't this be
    # handling the case with no checkoutUrl?" became error_handling for containing
    # "handle", and on ragnarok PR #3685 it swallowed a different, real finding five lines
    # away ("the Retry button never retries"). On a heavily commented PR that rule removed
    # exactly the findings that were new.
    overlap = _content_overlap(
        f"{new_finding.title} {new_finding.why}", existing.body or existing.title
    )
    same_category = new_finding.category.lower() == (existing.category or "").lower()
    if overlap >= _SAME_TOPIC_OVERLAP:
        return True
    if same_category and not existing.is_resolved and overlap >= _SAME_CATEGORY_OVERLAP:
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


# Share of the shorter text's content words that the other text also uses.
_SAME_TOPIC_OVERLAP = 0.5
_SAME_CATEGORY_OVERLAP = 0.3
_STOPWORDS = frozenset(
    "this that with from have been there their when what which would could should will "
    "into only also than then them they here case does done make made more most much "
    "such some other each just like need needs please".split()
)


def _content_words(text: str) -> set[str]:
    words = re.findall(r"[a-z][a-z0-9_]{3,}", (text or "").lower())
    return {word for word in words if word not in _STOPWORDS}


def _content_overlap(a: str, b: str) -> float:
    """Overlap coefficient of content words: 1.0 when the shorter text is fully covered."""
    words_a, words_b = _content_words(a), _content_words(b)
    if not words_a or not words_b:
        return 0.0
    return len(words_a & words_b) / min(len(words_a), len(words_b))
