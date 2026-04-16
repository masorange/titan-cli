"""Operations for compacting existing PR comments into prompt-ready context."""

from ..models.review_models import CommentContextEntry
from ..models.view import UICommentThread
from .manifest_operations import build_comment_review_context


def build_comment_context(
    review_threads: list[UICommentThread],
    general_comments: list[UICommentThread],
    max_entries: int,
    max_chars: int,
) -> list[CommentContextEntry]:
    """Build prompt-ready comment context using deterministic compression only."""

    return build_comment_review_context(
        review_threads=review_threads,
        general_comments=general_comments,
        max_entries=max_entries,
        max_chars=max_chars,
    )
