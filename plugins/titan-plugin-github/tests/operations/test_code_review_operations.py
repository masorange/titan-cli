"""
Tests for Code Review Operations

Tests for filter_own_duplicate_suggestions — ensures the AI cannot suggest
comments that the current user has already made, regardless of whether the AI
follows the prompt instructions.
"""

from titan_plugin_github.models.view import UIComment, UICommentThread, UIReviewSuggestion
from titan_plugin_github.operations.code_review_operations import (
    filter_own_duplicate_suggestions,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _comment(id: int, body: str, path: str = "src/foo.py", author: str = "finxo") -> UIComment:
    return UIComment(
        id=id,
        body=body,
        author_login=author,
        author_name=author,
        formatted_date="01/01/2026 00:00:00",
        path=path,
        line=10,
    )


def _thread(main: UIComment, replies: list = None) -> UICommentThread:
    return UICommentThread(
        thread_id=f"thread_{main.id}",
        main_comment=main,
        replies=replies or [],
        is_resolved=False,
        is_outdated=False,
    )


def _suggestion(
    body: str,
    file_path: str = "src/foo.py",
    reply_to: int = None,
) -> UIReviewSuggestion:
    return UIReviewSuggestion(
        file_path=file_path,
        line=10,
        body=body,
        severity="improvement",
        reply_to_comment_id=reply_to,
    )


# ---------------------------------------------------------------------------
# No own threads — nothing filtered
# ---------------------------------------------------------------------------

class TestFilterWithNoOwnThreads:
    def test_returns_all_suggestions_when_no_own_threads(self):
        suggestions = [_suggestion("This function is missing error handling")]
        kept, filtered = filter_own_duplicate_suggestions(suggestions, [])
        assert kept == suggestions
        assert filtered == []


# ---------------------------------------------------------------------------
# Reply-to-self filtering
# ---------------------------------------------------------------------------

class TestReplyToSelfFiltering:
    def test_filters_reply_to_own_comment(self):
        """AI should not reply to the user's own comment."""
        own_comment = _comment(id=42, body="Operations should not call services directly")
        own_threads = [_thread(own_comment)]

        suggestion = _suggestion(
            body="Operations should not call services directly",
            reply_to=42,
        )

        kept, filtered = filter_own_duplicate_suggestions([suggestion], own_threads)

        assert kept == []
        assert len(filtered) == 1

    def test_keeps_reply_to_other_reviewers_comment(self):
        """AI reply to another reviewer's comment should NOT be filtered."""
        own_comment = _comment(id=42, body="Operations should not call services")
        own_threads = [_thread(own_comment)]

        # Reply to someone else's comment
        suggestion = _suggestion(
            body="Actually this is wrong, operations should not call services",
            reply_to=99,  # pointing to other reviewer's comment
        )

        kept, filtered = filter_own_duplicate_suggestions([suggestion], own_threads)

        assert kept == [suggestion]
        assert filtered == []

    def test_filters_reply_to_own_reply(self):
        """AI should not reply to a reply that the user themselves wrote."""
        own_main = _comment(id=10, body="Initial comment")
        own_reply = _comment(id=20, body="Follow-up reply by same user")
        own_threads = [_thread(own_main, replies=[own_reply])]

        suggestion = _suggestion(body="Agreeing with the follow-up", reply_to=20)

        kept, filtered = filter_own_duplicate_suggestions([suggestion], own_threads)

        assert kept == []
        assert len(filtered) == 1


# ---------------------------------------------------------------------------
# Keyword duplicate filtering (new comment, no reply_to)
# ---------------------------------------------------------------------------

class TestKeywordDuplicateFiltering:
    def test_filters_duplicate_comment_on_same_file(self):
        """New comment with high keyword overlap on same file should be filtered."""
        own_comment = _comment(
            id=1,
            body="Operations should not call services directly, move this to the service layer",
            path="src/jira_client.py",
        )
        own_threads = [_thread(own_comment)]

        # AI says essentially the same thing
        suggestion = _suggestion(
            body="Operations are calling services directly. This should be moved to the service layer.",
            file_path="src/jira_client.py",
        )

        kept, filtered = filter_own_duplicate_suggestions([suggestion], own_threads)

        assert kept == []
        assert len(filtered) == 1

    def test_keeps_different_comment_on_same_file(self):
        """Different issue on same file should be kept."""
        own_comment = _comment(
            id=1,
            body="Operations should not call services directly",
            path="src/jira_client.py",
        )
        own_threads = [_thread(own_comment)]

        # AI raises a completely different issue
        suggestion = _suggestion(
            body="The return type annotation is missing on this method",
            file_path="src/jira_client.py",
        )

        kept, filtered = filter_own_duplicate_suggestions([suggestion], own_threads)

        assert kept == [suggestion]
        assert filtered == []

    def test_keeps_comment_on_different_file(self):
        """Same content on a different file should NOT be filtered."""
        own_comment = _comment(
            id=1,
            body="Operations should not call services directly",
            path="src/jira_client.py",
        )
        own_threads = [_thread(own_comment)]

        suggestion = _suggestion(
            body="Operations should not call services directly",
            file_path="src/other_client.py",  # different file
        )

        kept, filtered = filter_own_duplicate_suggestions([suggestion], own_threads)

        assert kept == [suggestion]
        assert filtered == []


# ---------------------------------------------------------------------------
# Mixed scenarios
# ---------------------------------------------------------------------------

class TestMixedScenarios:
    def test_filters_reply_to_self_and_duplicate_keeps_legit(self):
        """Reply-to-self and keyword duplicate are filtered; unrelated comment kept."""
        own_comment = _comment(
            id=42,
            body="Operations should not call services directly",
            path="src/jira_client.py",
        )
        own_threads = [_thread(own_comment)]

        reply_to_self = _suggestion(
            body="As I said, operations should not call services",
            file_path="src/jira_client.py",
            reply_to=42,
        )
        duplicate_new = _suggestion(
            body="Operations are calling services directly here",
            file_path="src/jira_client.py",
        )
        legit_comment = _suggestion(
            body="Missing unit tests for edge cases in this module",
            file_path="src/jira_client.py",
        )
        other_file = _suggestion(
            body="Null pointer risk here",
            file_path="src/unrelated.py",
        )

        kept, filtered = filter_own_duplicate_suggestions(
            [reply_to_self, duplicate_new, legit_comment, other_file],
            own_threads,
        )

        assert legit_comment in kept
        assert other_file in kept
        assert reply_to_self in filtered
        assert duplicate_new in filtered

    def test_no_suggestions_returns_empty(self):
        own_comment = _comment(id=1, body="Some issue")
        own_threads = [_thread(own_comment)]

        kept, filtered = filter_own_duplicate_suggestions([], own_threads)

        assert kept == []
        assert filtered == []
