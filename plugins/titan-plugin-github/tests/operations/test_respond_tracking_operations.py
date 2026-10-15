"""Tests for the run record: the link between a comment, a decision and a commit."""

import pytest

from titan_plugin_github.models.review_enums import CommentVerdictType
from titan_plugin_github.models.review_models import CommentVerdict
from titan_plugin_github.operations.respond_tracking_operations import (
    build_decision_row,
    build_run_record,
    run_record_path,
    verdict_agreement,
)


def _verdict(kind: CommentVerdictType, comment_id: int = 1) -> CommentVerdict:
    return CommentVerdict(comment_id=comment_id, verdict=kind, reason="because")


@pytest.mark.unit
class TestVerdictAgreement:
    @pytest.mark.parametrize("choice", ["ai_review", "change_manually"])
    def test_changing_the_code_agrees_with_apply(self, choice):
        assert verdict_agreement("apply", choice) is True

    @pytest.mark.parametrize("choice", ["ai_review", "change_manually"])
    def test_changing_the_code_overrules_the_other_verdicts(self, choice):
        assert verdict_agreement("wrong", choice) is False
        assert verdict_agreement("already_done", choice) is False

    @pytest.mark.parametrize("choice", ["use_reply", "reply", "resolve"])
    def test_answering_without_changing_agrees_with_the_non_apply_verdicts(self, choice):
        assert verdict_agreement("wrong", choice) is True
        assert verdict_agreement("needs_discussion", choice) is True
        assert verdict_agreement("apply", choice) is False

    def test_skip_and_exit_say_nothing_about_the_verdict(self):
        """Neither is a judgement of the session; counting them as disagreement would lie."""
        assert verdict_agreement("apply", "skip") is None
        assert verdict_agreement("apply", "exit") is None

    def test_no_verdict_means_no_question(self):
        assert verdict_agreement(None, "ai_review") is None
        assert verdict_agreement("apply", None) is None


@pytest.mark.unit
class TestBuildDecisionRow:
    def test_carries_the_comment_the_verdict_and_the_commit(self, sample_ui_comment_thread):
        row = build_decision_row(
            sample_ui_comment_thread,
            _verdict(CommentVerdictType.APPLY),
            "ai_review",
            "abc12345",
            replied=False,
        )

        assert row["comment_id"] == sample_ui_comment_thread.main_comment.id
        assert row["path"] == "src/main.py"
        assert row["verdict"] == "apply"
        assert row["choice"] == "ai_review"
        assert row["agreed_with_verdict"] is True
        assert row["commit"] == "abc12345"

    def test_a_comment_nobody_judged(self, sample_ui_comment_thread):
        row = build_decision_row(sample_ui_comment_thread, None, "skip", None, replied=False)

        assert row["verdict"] is None
        assert row["agreed_with_verdict"] is None


@pytest.mark.unit
class TestBuildRunRecord:
    def test_counts_what_a_score_is_read_off(self, sample_ui_comment_thread):
        rows = [
            build_decision_row(
                sample_ui_comment_thread, _verdict(CommentVerdictType.APPLY), "ai_review", "aaa", False
            ),
            build_decision_row(
                sample_ui_comment_thread, _verdict(CommentVerdictType.WRONG), "ai_review", "bbb", False
            ),
            build_decision_row(sample_ui_comment_thread, None, "skip", None, False),
        ]

        record = build_run_record("run123", 276, "headsha", {"cli": "claude"}, rows)

        assert record["run"] == "run123"
        assert record["pr"] == 276
        assert record["comments"] == 3
        assert record["agreed"] == 1
        assert record["overruled"] == 1
        assert record["not_judged"] == 1
        assert record["choices"] == {"ai_review": 2, "skip": 1}
        assert record["judgement"] == {"cli": "claude"}

    def test_commits_are_indexed_by_comment(self, sample_ui_comment_thread):
        """This index is what attributes a later review's finding to the comment it came from."""
        comment_id = sample_ui_comment_thread.main_comment.id
        rows = [
            build_decision_row(
                sample_ui_comment_thread, _verdict(CommentVerdictType.APPLY), "ai_review", "deadbeef", False
            )
        ]

        record = build_run_record("r", 1, None, {}, rows)

        assert record["commits"] == {str(comment_id): "deadbeef"}

    def test_a_run_with_no_judging_session_is_still_a_row(self, sample_ui_comment_thread):
        """The baseline variant: no verdicts, which the record has to be able to say."""
        rows = [build_decision_row(sample_ui_comment_thread, None, "ai_review", "aaa", False)]

        record = build_run_record(None, 1, None, {}, rows)

        assert record["judgement"] == {}
        assert record["not_judged"] == 1
        assert record["agreed"] == 0 and record["overruled"] == 0

    def test_path_is_per_run(self):
        assert run_record_path("abc123") == "runs/abc123.json"
        assert run_record_path(None) == "runs/unknown.json"
