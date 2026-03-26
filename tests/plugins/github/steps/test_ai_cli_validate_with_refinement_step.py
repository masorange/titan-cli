"""
Tests for titan_plugin_github.steps.ai_cli_validate_with_refinement_step.

The refinement loop relies on threading.Event and mounting Textual widgets, so
_run_refinement_loop is mocked in most tests. Dedicated tests cover its logic
directly by simulating the decision callback.
"""

import unittest
from unittest.mock import MagicMock, patch

from titan_cli.core.models.code_review import (
    CodeReviewSessionResult,
    RefinementAction,
    RefinementIteration,
    UserDecision,
)
from titan_cli.engine.results import Error, Skip, Success
from titan_cli.external_cli.adapters.base import HeadlessResponse, SupportedCLI


_MODULE = "titan_plugin_github.steps.ai_cli_validate_with_refinement_step"


def _make_ctx(data: dict | None = None) -> MagicMock:
    ctx = MagicMock()
    ctx.data = data or {}
    ctx.get = lambda key, default=None: ctx.data.get(key, default)
    ctx.textual.loading.return_value.__enter__ = MagicMock(return_value=None)
    ctx.textual.loading.return_value.__exit__ = MagicMock(return_value=False)
    return ctx


def _make_thread(comment_id: int = 1, body: str = "Why not X?") -> MagicMock:
    thread = MagicMock()
    thread.main_comment.id = comment_id
    thread.main_comment.body = body
    thread.main_comment.author_login = "reviewer"
    thread.replies = []
    return thread


def _make_adapter(stdout: str = "Good point!", exit_code: int = 0, available: bool = True) -> MagicMock:
    adapter = MagicMock()
    adapter.cli_name = SupportedCLI.CLAUDE
    adapter.is_available.return_value = available
    adapter.execute.return_value = HeadlessResponse(
        stdout=stdout, stderr="", exit_code=exit_code,
    )
    return adapter


# ── Early exits ───────────────────────────────────────────────────────────────

class TestEarlyExits(unittest.TestCase):

    def test_no_threads_returns_skip(self):
        from titan_plugin_github.steps.ai_cli_validate_with_refinement_step import ai_cli_validate_with_refinement
        ctx = _make_ctx({})
        result = ai_cli_validate_with_refinement(ctx)
        self.assertIsInstance(result, Skip)

    def test_empty_threads_list_returns_skip(self):
        from titan_plugin_github.steps.ai_cli_validate_with_refinement_step import ai_cli_validate_with_refinement
        ctx = _make_ctx({"review_threads": []})
        result = ai_cli_validate_with_refinement(ctx)
        self.assertIsInstance(result, Skip)

    def test_invalid_cli_preference_returns_error(self):
        from titan_plugin_github.steps.ai_cli_validate_with_refinement_step import ai_cli_validate_with_refinement
        ctx = _make_ctx({"review_threads": [_make_thread()], "cli_preference": "openai"})
        result = ai_cli_validate_with_refinement(ctx)
        self.assertIsInstance(result, Error)

    @patch(f"{_MODULE}.get_headless_adapter")
    @patch(f"{_MODULE}.HEADLESS_ADAPTER_REGISTRY", {SupportedCLI.CLAUDE: None})
    def test_no_adapter_returns_error(self, mock_get):
        from titan_plugin_github.steps.ai_cli_validate_with_refinement_step import ai_cli_validate_with_refinement
        mock_get.return_value = _make_adapter(available=False)
        ctx = _make_ctx({"review_threads": [_make_thread()]})
        result = ai_cli_validate_with_refinement(ctx)
        self.assertIsInstance(result, Error)


# ── Happy path: approve and reject ────────────────────────────────────────────

class TestApproveAndReject(unittest.TestCase):

    @patch(f"{_MODULE}._run_refinement_loop", return_value=UserDecision.APPROVED)
    @patch(f"{_MODULE}.parse_reply_suggestion", return_value="Great suggestion")
    @patch(f"{_MODULE}.build_refinement_prompt", return_value="prompt")
    @patch(f"{_MODULE}.get_headless_adapter")
    @patch(f"{_MODULE}.HEADLESS_ADAPTER_REGISTRY", {SupportedCLI.CLAUDE: None})
    def test_approved_session_stored(self, mock_get, _build, _parse, _loop):
        from titan_plugin_github.steps.ai_cli_validate_with_refinement_step import ai_cli_validate_with_refinement
        mock_get.return_value = _make_adapter()

        ctx = _make_ctx({"review_threads": [_make_thread(comment_id=99)]})
        result = ai_cli_validate_with_refinement(ctx)

        self.assertIsInstance(result, Success)
        session_result: CodeReviewSessionResult = ctx.data["code_review_session_result"]
        self.assertIn(99, session_result.comment_sessions)
        session = session_result.comment_sessions[99]
        self.assertEqual(session.user_decision, UserDecision.APPROVED)
        self.assertEqual(session.final_suggestion, "Great suggestion")

    @patch(f"{_MODULE}._run_refinement_loop", return_value=UserDecision.REJECTED)
    @patch(f"{_MODULE}.parse_reply_suggestion", return_value="suggestion")
    @patch(f"{_MODULE}.build_refinement_prompt", return_value="prompt")
    @patch(f"{_MODULE}.get_headless_adapter")
    @patch(f"{_MODULE}.HEADLESS_ADAPTER_REGISTRY", {SupportedCLI.CLAUDE: None})
    def test_rejected_session_has_no_final_suggestion(self, mock_get, _build, _parse, _loop):
        from titan_plugin_github.steps.ai_cli_validate_with_refinement_step import ai_cli_validate_with_refinement
        mock_get.return_value = _make_adapter()

        ctx = _make_ctx({"review_threads": [_make_thread(comment_id=7)]})
        ai_cli_validate_with_refinement(ctx)

        session_result: CodeReviewSessionResult = ctx.data["code_review_session_result"]
        session = session_result.comment_sessions[7]
        self.assertEqual(session.user_decision, UserDecision.REJECTED)
        self.assertIsNone(session.final_suggestion)

    @patch(f"{_MODULE}._run_refinement_loop", return_value=UserDecision.APPROVED)
    @patch(f"{_MODULE}.parse_reply_suggestion", return_value="s")
    @patch(f"{_MODULE}.build_refinement_prompt", return_value="p")
    @patch(f"{_MODULE}.get_headless_adapter")
    @patch(f"{_MODULE}.HEADLESS_ADAPTER_REGISTRY", {SupportedCLI.CLAUDE: None})
    def test_custom_output_key(self, mock_get, _b, _p, _loop):
        from titan_plugin_github.steps.ai_cli_validate_with_refinement_step import ai_cli_validate_with_refinement
        mock_get.return_value = _make_adapter()
        ctx = _make_ctx({
            "review_threads": [_make_thread()],
            "output_key": "my_result",
        })
        ai_cli_validate_with_refinement(ctx)
        self.assertIn("my_result", ctx.data)


# ── Initial suggestion failure ────────────────────────────────────────────────

class TestInitialSuggestionFailure(unittest.TestCase):

    @patch(f"{_MODULE}.get_headless_adapter")
    @patch(f"{_MODULE}.HEADLESS_ADAPTER_REGISTRY", {SupportedCLI.CLAUDE: None})
    def test_failed_initial_response_skips_thread(self, mock_get):
        from titan_plugin_github.steps.ai_cli_validate_with_refinement_step import ai_cli_validate_with_refinement
        mock_get.return_value = _make_adapter(exit_code=1)

        ctx = _make_ctx({"review_threads": [_make_thread(comment_id=5)]})
        result = ai_cli_validate_with_refinement(ctx)

        self.assertIsInstance(result, Success)
        session_result: CodeReviewSessionResult = ctx.data["code_review_session_result"]
        # Thread was skipped — not added to comment_sessions
        self.assertNotIn(5, session_result.comment_sessions)


# ── Initial findings carried over ─────────────────────────────────────────────

class TestInitialFindingsCarryOver(unittest.TestCase):

    @patch(f"{_MODULE}._run_refinement_loop", return_value=UserDecision.REJECTED)
    @patch(f"{_MODULE}.parse_reply_suggestion", return_value="s")
    @patch(f"{_MODULE}.build_refinement_prompt", return_value="p")
    @patch(f"{_MODULE}.get_headless_adapter")
    @patch(f"{_MODULE}.HEADLESS_ADAPTER_REGISTRY", {SupportedCLI.CLAUDE: None})
    def test_initial_findings_included_in_result(self, mock_get, _b, _p, _loop):
        from titan_plugin_github.steps.ai_cli_validate_with_refinement_step import ai_cli_validate_with_refinement
        from titan_cli.core.models.code_review import ReviewFinding, ReviewSeverity
        mock_get.return_value = _make_adapter()

        findings = [ReviewFinding(severity=ReviewSeverity.HIGH, title="Issue", description="Desc")]
        ctx = _make_ctx({
            "review_threads": [_make_thread()],
            "initial_review_findings": findings,
        })
        ai_cli_validate_with_refinement(ctx)

        session_result: CodeReviewSessionResult = ctx.data["code_review_session_result"]
        self.assertEqual(session_result.findings_initial, findings)


# ── _run_refinement_loop unit tests ──────────────────────────────────────────

class TestRefinementLoop(unittest.TestCase):
    """
    Tests for _run_refinement_loop by directly invoking it with a controlled ctx.
    The loop uses threading.Event internally; we simulate decisions by making
    ctx.textual.mount() trigger the on_select callback synchronously.
    """

    def _invoke_loop_with_decision(self, action: RefinementAction) -> UserDecision:
        """Helper: run the loop and immediately fire the given action."""
        from titan_plugin_github.steps.ai_cli_validate_with_refinement_step import _run_refinement_loop
        from titan_cli.core.models.code_review import CommentReviewSession

        ctx = _make_ctx()

        # When the step calls ctx.textual.mount(widget), fire on_select immediately
        def mount_side_effect(widget):
            widget.on_select_callback(action)

        ctx.textual.mount.side_effect = mount_side_effect

        session = CommentReviewSession(
            comment_id=1,
            original_comment="Why not X?",
            existing_replies=[],
            iterations=[RefinementIteration(iteration_number=1, agent_suggestion="Use Y instead")],
        )

        return _run_refinement_loop(
            ctx=ctx,
            session=session,
            thread=_make_thread(),
            thread_idx=0,
            total_threads=1,
            adapter=_make_adapter(),
            diff="diff",
            project_root=None,
            timeout=30,
            max_iterations=4,
            cli_display="Claude",
        )

    def test_approve_returns_approved(self):
        result = self._invoke_loop_with_decision(RefinementAction.APPROVE)
        self.assertEqual(result, UserDecision.APPROVED)

    def test_reject_returns_rejected(self):
        result = self._invoke_loop_with_decision(RefinementAction.REJECT)
        self.assertEqual(result, UserDecision.REJECTED)

    def test_refine_then_approve_adds_iteration(self):
        from titan_plugin_github.steps.ai_cli_validate_with_refinement_step import _run_refinement_loop
        from titan_cli.core.models.code_review import CommentReviewSession

        ctx = _make_ctx()
        ctx.textual.ask_multiline.return_value = "add null check"

        actions = iter([RefinementAction.REFINE, RefinementAction.APPROVE])

        def mount_side_effect(widget):
            widget.on_select_callback(next(actions))

        ctx.textual.mount.side_effect = mount_side_effect

        adapter = _make_adapter(stdout="Better suggestion with null check")

        session = CommentReviewSession(
            comment_id=1,
            original_comment="Missing null check",
            existing_replies=[],
            iterations=[RefinementIteration(iteration_number=1, agent_suggestion="Add X")],
        )

        result = _run_refinement_loop(
            ctx=ctx,
            session=session,
            thread=_make_thread(),
            thread_idx=0,
            total_threads=1,
            adapter=adapter,
            diff="",
            project_root=None,
            timeout=30,
            max_iterations=4,
            cli_display="Claude",
        )

        self.assertEqual(result, UserDecision.APPROVED)
        self.assertEqual(session.iteration_count, 2)
        self.assertEqual(session.iterations[-1].user_feedback, "add null check")

    def test_empty_feedback_does_not_add_iteration(self):
        from titan_plugin_github.steps.ai_cli_validate_with_refinement_step import _run_refinement_loop
        from titan_cli.core.models.code_review import CommentReviewSession

        ctx = _make_ctx()
        # First refine with empty feedback, then reject
        ctx.textual.ask_multiline.return_value = "   "  # blank
        actions = iter([RefinementAction.REFINE, RefinementAction.REJECT])

        def mount_side_effect(widget):
            widget.on_select_callback(next(actions))

        ctx.textual.mount.side_effect = mount_side_effect

        session = CommentReviewSession(
            comment_id=1,
            original_comment="Comment",
            existing_replies=[],
            iterations=[RefinementIteration(iteration_number=1, agent_suggestion="Suggestion")],
        )

        result = _run_refinement_loop(
            ctx=ctx,
            session=session,
            thread=_make_thread(),
            thread_idx=0,
            total_threads=1,
            adapter=_make_adapter(),
            diff="",
            project_root=None,
            timeout=30,
            max_iterations=4,
            cli_display="Claude",
        )

        self.assertEqual(result, UserDecision.REJECTED)
        # No new iteration added — feedback was blank
        self.assertEqual(session.iteration_count, 1)


if __name__ == "__main__":
    unittest.main()
