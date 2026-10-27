"""Tests for the judging session's prompt, answer and files."""

import json

import pytest

from titan_cli.core.result import ClientError, ClientSuccess
from titan_plugin_github.models.review_enums import CommentVerdictType
from titan_plugin_github.models.review_models import CommentVerdict
from titan_plugin_github.operations.comment_judgement_operations import (
    build_fix_session_prompt,
    build_judgement_prompt,
    judgement_json_schema,
    parse_judgement_response,
    render_comments_file,
    render_verdict_file,
    to_verdict,
    verdict_file_path,
)


@pytest.mark.unit
class TestRenderCommentsFile:
    def test_carries_the_id_the_answer_must_use(self, sample_ui_comment_thread):
        rendered = render_comments_file([sample_ui_comment_thread])

        assert f"comment_id {sample_ui_comment_thread.main_comment.id}" in rendered
        assert "src/main.py:42" in rendered

    def test_includes_every_reply(self, sample_ui_comment_thread):
        """A comment answered further down its own thread reads as 'apply' without them."""
        rendered = render_comments_file([sample_ui_comment_thread])

        for reply in sample_ui_comment_thread.replies:
            assert reply.body in rendered

    def test_empty_list(self):
        assert "(none)" in render_comments_file([])


@pytest.mark.unit
class TestBuildJudgementPrompt:
    def test_names_the_repository_and_the_material(self):
        prompt = build_judgement_prompt(
            276, "A title", "head", "base", "/home/u/repo", "/home/u/repo/.titan-review", 4
        )

        assert "/home/u/repo" in prompt
        assert "/home/u/repo/.titan-review" in prompt
        assert "comments.md" in prompt
        assert "4 review comment(s)" in prompt

    def test_material_files_are_named_relative_to_the_material_directory(self):
        """`material_dir` already IS `.titan-review`, so the constants' prefix would send the
        session to `<material_dir>/.titan-review/pr.md`, which does not exist."""
        prompt = build_judgement_prompt(
            276, "t", "h", "b", "/repo", "/repo/.titan-review", 1
        )

        assert "`pr.md`" in prompt and "`pr.diff`" in prompt
        assert ".titan-review/pr.md" not in prompt
        assert ".titan-review/diffs" not in prompt

    def test_offers_the_four_verdicts(self):
        prompt = build_judgement_prompt(1, "t", "h", "b", "/r", "/m", 1)

        for verdict in CommentVerdictType:
            assert f"`{verdict.value}`" in prompt

    def test_asks_for_callers_because_the_fix_session_starts_blind(self):
        prompt = build_judgement_prompt(1, "t", "h", "b", "/r", "/m", 1)

        assert "callers_to_check" in prompt
        assert "files_affected" in prompt
        assert "do not run tests" in prompt.lower()

    def test_subagents_only_when_the_cli_has_them(self):
        assert "subagents" not in build_judgement_prompt(1, "t", "h", "b", "/r", "/m", 1)
        assert "subagents" in build_judgement_prompt(
            1, "t", "h", "b", "/r", "/m", 1, use_subagents=True
        )


@pytest.mark.unit
class TestParseJudgementResponse:
    def test_reads_the_envelope(self):
        payload = json.dumps({"verdicts": [{"comment_id": 1}]})

        match parse_judgement_response(payload, structured=True):
            case ClientSuccess(data=verdicts):
                assert verdicts == [{"comment_id": 1}]
            case other:
                pytest.fail(f"expected success, got {other}")

    def test_reads_a_bare_array_from_a_cli_without_a_schema(self):
        match parse_judgement_response('[{"comment_id": 2}]', structured=False):
            case ClientSuccess(data=verdicts):
                assert verdicts == [{"comment_id": 2}]
            case other:
                pytest.fail(f"expected success, got {other}")

    def test_structured_answer_missing_the_field_is_an_error(self):
        match parse_judgement_response('{"findings": []}', structured=True):
            case ClientError(error_code=code):
                assert code == "MISSING_VERDICTS_FIELD"
            case other:
                pytest.fail(f"expected error, got {other}")

    def test_comment_id_is_a_single_type(self):
        """The CLI validates the schema in Ajv strict mode, which rejects `integer|string`
        ("use allowUnionTypes ... strictTypes") and makes the session answer with nothing."""
        props = judgement_json_schema()["properties"]["verdicts"]["items"]["properties"]

        assert props["comment_id"] == {"type": "integer"}
        for field in ("risk", "proposed_fix", "reply_draft"):
            # Unions WITH null are what strict mode tolerates.
            assert "null" in props[field]["type"]

    def test_schema_allows_only_the_known_verdicts(self):
        schema = judgement_json_schema()
        allowed = schema["properties"]["verdicts"]["items"]["properties"]["verdict"]["enum"]

        assert set(allowed) == {v.value for v in CommentVerdictType}


@pytest.mark.unit
class TestToVerdict:
    def test_accepts_a_digit_string_id(self):
        """A CLI without structured output answers with strings."""
        verdict = to_verdict({"comment_id": "7", "verdict": "apply", "reason": "r"}, {7})

        assert verdict is not None
        assert verdict.comment_id == 7

    def test_drops_an_id_that_is_not_being_judged(self):
        """An invented id would otherwise answer the wrong thread."""
        assert to_verdict({"comment_id": 99, "verdict": "apply", "reason": "r"}, {7}) is None

    def test_drops_an_unknown_verdict(self):
        assert to_verdict({"comment_id": 7, "verdict": "maybe", "reason": "r"}, {7}) is None

    def test_drops_a_verdict_with_no_reason(self):
        """The user judges the verdict by its reason; without one there is nothing to judge."""
        assert to_verdict({"comment_id": 7, "verdict": "apply", "reason": "  "}, {7}) is None

    def test_normalises_the_lists_and_the_optional_text(self):
        verdict = to_verdict(
            {
                "comment_id": 7,
                "verdict": "WRONG",
                "reason": "already handled",
                "files_affected": "a.py",
                "callers_to_check": ["b.py", "", None],
                "risk": "",
                "reply_draft": "No change needed.",
            },
            {7},
        )

        assert verdict.verdict == CommentVerdictType.WRONG
        assert verdict.files_affected == ["a.py"]
        assert verdict.callers_to_check == ["b.py"]
        assert verdict.risk is None
        assert verdict.reply_draft == "No change needed."

    def test_drops_a_non_dict(self):
        assert to_verdict("apply", {7}) is None


@pytest.mark.unit
class TestVerdictFile:
    def test_path_is_per_comment(self):
        assert verdict_file_path(12) == "verdicts/comment-12.md"

    def test_file_carries_the_analysis_the_fix_session_lacks(self, sample_ui_comment_thread):
        verdict = CommentVerdict(
            comment_id=sample_ui_comment_thread.main_comment.id,
            verdict=CommentVerdictType.APPLY,
            reason="The second caller is not guarded",
            files_affected=["steps/code_review_steps.py"],
            callers_to_check=["workflows/review-pr-thread-resolution.yaml"],
            risk="Thread resolution would always warn",
            proposed_fix="Record that the review ran",
        )

        rendered = render_verdict_file(verdict, sample_ui_comment_thread)

        assert "The second caller is not guarded" in rendered
        assert "steps/code_review_steps.py" in rendered
        assert "review-pr-thread-resolution.yaml" in rendered
        assert "Thread resolution would always warn" in rendered
        assert "Record that the review ran" in rendered
        assert sample_ui_comment_thread.main_comment.body in rendered

    def test_fix_prompt_points_at_the_verdict_and_keeps_the_response_path(self):
        prompt = build_fix_session_prompt("/m/verdicts/comment-3.md", "/tmp/r.txt")

        assert "/m/verdicts/comment-3.md" in prompt
        assert "/tmp/r.txt" in prompt
        assert "caller" in prompt.lower()
        # The assistant step formats the template; a stray brace would raise there.
        assert prompt.format(context="x") == prompt
