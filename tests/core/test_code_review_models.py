"""Tests for core.models.code_review."""

import unittest

from titan_cli.core.models.code_review import (
    CodeReviewSessionResult,
    CommentReviewSession,
    RefinementIteration,
    ReviewFinding,
    ReviewSeverity,
    UserDecision,
)


class TestReviewSeverity(unittest.TestCase):

    def test_values_are_strings(self):
        self.assertEqual(ReviewSeverity.CRITICAL, "critical")
        self.assertEqual(ReviewSeverity.HIGH, "high")
        self.assertEqual(ReviewSeverity.MEDIUM, "medium")
        self.assertEqual(ReviewSeverity.LOW, "low")


class TestReviewFinding(unittest.TestCase):

    def _make(self, severity=ReviewSeverity.HIGH, title="Bad code", **kwargs) -> ReviewFinding:
        return ReviewFinding(severity=severity, title=title, description="desc", **kwargs)

    def test_emoji_critical(self):
        self.assertEqual(self._make(severity=ReviewSeverity.CRITICAL).emoji, "🔴")

    def test_emoji_high(self):
        self.assertEqual(self._make(severity=ReviewSeverity.HIGH).emoji, "🟡")

    def test_emoji_medium(self):
        self.assertEqual(self._make(severity=ReviewSeverity.MEDIUM).emoji, "🟢")

    def test_emoji_low(self):
        self.assertEqual(self._make(severity=ReviewSeverity.LOW).emoji, "🟠")

    def test_display_header_with_file_and_line(self):
        f = self._make(file="foo.py", line=42)
        self.assertIn("foo.py", f.display_header)
        self.assertIn("42", f.display_header)

    def test_display_header_without_file(self):
        f = self._make()
        self.assertNotIn("`", f.display_header)

    def test_display_header_with_file_no_line(self):
        f = self._make(file="bar.py")
        self.assertIn("bar.py", f.display_header)
        self.assertNotIn(":", f.display_header.split("bar.py")[1])


class TestCommentReviewSession(unittest.TestCase):

    def _make_session(self) -> CommentReviewSession:
        return CommentReviewSession(
            comment_id=1,
            original_comment="Why not use X?",
        )

    def test_current_suggestion_none_when_no_iterations(self):
        session = self._make_session()
        self.assertIsNone(session.current_suggestion)

    def test_current_suggestion_returns_last(self):
        session = self._make_session()
        session.iterations.append(RefinementIteration(iteration_number=1, agent_suggestion="Use X"))
        session.iterations.append(RefinementIteration(iteration_number=2, agent_suggestion="Use Y"))
        self.assertEqual(session.current_suggestion, "Use Y")

    def test_iteration_count(self):
        session = self._make_session()
        session.iterations.append(RefinementIteration(iteration_number=1, agent_suggestion="A"))
        self.assertEqual(session.iteration_count, 1)

    def test_is_decided_pending(self):
        session = self._make_session()
        self.assertFalse(session.is_decided)

    def test_is_decided_approved(self):
        session = self._make_session()
        session.user_decision = UserDecision.APPROVED
        self.assertTrue(session.is_decided)

    def test_is_decided_rejected(self):
        session = self._make_session()
        session.user_decision = UserDecision.REJECTED
        self.assertTrue(session.is_decided)


class TestCodeReviewSessionResult(unittest.TestCase):

    def _make_session(self, comment_id: int, decision: UserDecision) -> CommentReviewSession:
        s = CommentReviewSession(comment_id=comment_id, original_comment="comment")
        s.user_decision = decision
        s.iterations.append(RefinementIteration(iteration_number=1, agent_suggestion="suggestion"))
        return s

    def test_total_iterations(self):
        result = CodeReviewSessionResult()
        result.comment_sessions[1] = self._make_session(1, UserDecision.APPROVED)
        result.comment_sessions[2] = self._make_session(2, UserDecision.REJECTED)
        self.assertEqual(result.total_iterations, 2)

    def test_approved_sessions(self):
        result = CodeReviewSessionResult()
        result.comment_sessions[1] = self._make_session(1, UserDecision.APPROVED)
        result.comment_sessions[2] = self._make_session(2, UserDecision.REJECTED)
        self.assertEqual(len(result.approved_sessions), 1)
        self.assertEqual(result.approved_sessions[0].comment_id, 1)

    def test_approval_rate_all_approved(self):
        result = CodeReviewSessionResult()
        result.comment_sessions[1] = self._make_session(1, UserDecision.APPROVED)
        result.comment_sessions[2] = self._make_session(2, UserDecision.APPROVED)
        self.assertAlmostEqual(result.approval_rate, 1.0)

    def test_approval_rate_half(self):
        result = CodeReviewSessionResult()
        result.comment_sessions[1] = self._make_session(1, UserDecision.APPROVED)
        result.comment_sessions[2] = self._make_session(2, UserDecision.REJECTED)
        self.assertAlmostEqual(result.approval_rate, 0.5)

    def test_approval_rate_no_decided(self):
        result = CodeReviewSessionResult()
        result.comment_sessions[1] = self._make_session(1, UserDecision.PENDING)
        self.assertAlmostEqual(result.approval_rate, 0.0)

    def test_empty_result(self):
        result = CodeReviewSessionResult()
        self.assertEqual(result.total_iterations, 0)
        self.assertEqual(result.approved_sessions, [])
        self.assertAlmostEqual(result.approval_rate, 0.0)


if __name__ == "__main__":
    unittest.main()
