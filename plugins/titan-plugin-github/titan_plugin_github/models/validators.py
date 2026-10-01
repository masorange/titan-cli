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

    finding_text = f"{new_finding.title} {new_finding.why}"
    comment_text = existing.body or existing.title
    overlap = _content_overlap(finding_text, comment_text)

    if existing.is_bot:
        # A bot comment is generic text pinned to a line: the same line is the only
        # signal that a finding is about the same thing.
        return (
            new_finding.line is not None
            and new_finding.line == existing.line
            and overlap >= _SAME_LINE_OVERLAP
        )

    # Two texts that name the same code identifiers (`previous_version_code`,
    # `versionPropsFile`) are about the same code even when one anchors a few lines from
    # the other: the same defect reported at the declaration and at the comparison sat
    # 8 lines apart, past the plain window, and was posted twice (#3735).
    shared_identifiers = _identifiers(finding_text) & _identifiers(comment_text)
    window = max(line_proximity_window, _IDENTIFIER_WINDOW) if shared_identifiers else line_proximity_window
    if not _lines_are_close(new_finding.line, existing.line, window):
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
    same_category = new_finding.category.lower() == (existing.category or "").lower()
    if overlap >= _SAME_TOPIC_OVERLAP:
        return True
    if shared_identifiers and overlap >= _SHARED_IDENTIFIER_OVERLAP:
        return True
    # The exact same line is a stronger signal than the window: ragnarok #3723 re-reported
    # two findings already commented on the very line they anchor to, at overlaps of 0.29
    # and 0.39, because the comments' guessed category differed. The case that made the
    # thresholds strict (#3685) was a different defect five lines away, not on the line.
    if (
        new_finding.line is not None
        and new_finding.line == existing.line
        and overlap >= _SAME_LINE_OVERLAP
    ):
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
_SAME_LINE_OVERLAP = 0.25
_SHARED_IDENTIFIER_OVERLAP = 0.25
# How far apart two comments may sit when they name the same code identifier.
_IDENTIFIER_WINDOW = 15
_IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z0-9_]{5,}")
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


def _identifiers(text: str) -> set[str]:
    """Code identifiers in a text: snake_case or camelCase words, which prose does not use."""
    return {
        token.lower()
        for token in _IDENTIFIER.findall(text or "")
        if "_" in token or re.search(r"[a-z][A-Z]", token)
    }
