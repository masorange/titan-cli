# plugins/titan-plugin-github/titan_plugin_github/models/mappers/thread_mapper.py
"""
Thread Mappers

Converts network models (GraphQL) to view models (UI).
"""
from typing import List

from ..network.graphql import GraphQLPullRequestReviewThread
from ..view import UIComment, UICommentThread
from .comment_mapper import from_graphql_review_comment


def from_graphql_review_thread(thread: GraphQLPullRequestReviewThread) -> UICommentThread:
    """
    Convert GraphQL review thread to UI comment thread.

    Args:
        thread: GraphQLPullRequestReviewThread from GraphQL API

    Returns:
        UICommentThread ready for rendering
    """
    # Convert all comments with outdated status
    ui_comments: List[UIComment] = [
        from_graphql_review_comment(comment, is_outdated=thread.isOutdated)
        for comment in thread.comments
    ]

    # Split into main + replies
    main_comment = ui_comments[0] if ui_comments else None
    replies = ui_comments[1:] if len(ui_comments) > 1 else []

    return UICommentThread(
        thread_id=thread.id,
        main_comment=main_comment,
        replies=replies,
        is_resolved=thread.isResolved,
        is_outdated=thread.isOutdated
    )
