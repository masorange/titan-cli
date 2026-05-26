"""Shared formatting helpers for AI review prompts."""

import json

from ..models.review_models import CommentContextEntry


def comment_context_to_json(comments: list[CommentContextEntry]) -> str:
    """Serialize compact comment context entries for prompt embedding."""
    return json.dumps(
        [
            {
                "kind": entry.kind,
                "path": entry.path,
                "line": entry.line,
                "category": entry.category,
                "title": entry.title,
                "summary": entry.summary,
                "is_resolved": entry.is_resolved,
            }
            for entry in comments
        ],
        indent=2,
    )
