"""Tests for the judging step: what it publishes, and what it does when it cannot run.

The step's promise is that a failure never costs the user the workflow: without verdicts the
comments are shown exactly as they were before it existed. That degradation is what these
tests pin, next to the happy path's contract (verdicts by comment id, verdict files on disk).
"""

import json
from pathlib import Path
from unittest.mock import Mock

import pytest

from titan_cli.engine import WorkflowContext
from titan_cli.engine.results import Success
from titan_plugin_github.models.review_enums import CommentVerdictType
import titan_plugin_github.steps.pr_review_steps as pr_review_steps
from titan_plugin_github.steps.pr_review_steps import judge_pr_comments_step

from .test_code_review_steps import _FakeTextual


def _ctx(tmp_path, threads) -> WorkflowContext:
    ctx = WorkflowContext()
    ctx.textual = _FakeTextual()
    ctx.git = Mock()
    ctx.github = Mock()
    ctx.data["selected_pr_number"] = 276
    ctx.data["pending_comment_threads"] = threads
    ctx.data["project_root"] = str(tmp_path)
    return ctx


def _adapter(stdout: str, *, succeeded: bool = True):
    adapter = Mock()
    adapter.supports_subagents = False
    adapter.supports_structured_output = True
    adapter.supports_tool_restriction = True
    adapter.supports_effort_control = True
    adapter.cli_name = Mock(value="claude")
    response = Mock()
    response.succeeded = succeeded
    response.exit_code = 0 if succeeded else 1
    response.stdout = stdout
    response.stderr = ""
    adapter.execute.return_value = response
    return adapter


@pytest.mark.unit
def test_without_a_cli_it_publishes_no_verdicts_and_does_not_fail(
    monkeypatch, tmp_path, sample_ui_comment_thread
):
    """AI off or no CLI: the workflow carries on asking comment by comment."""
    monkeypatch.setattr(
        "titan_plugin_github.steps.code_review_steps.resolve_review_adapter",
        lambda ctx, step: (None, "no CLI available", False),
    )

    result = judge_pr_comments_step(_ctx(tmp_path, [sample_ui_comment_thread]))

    assert isinstance(result, Success)
    assert result.metadata["comment_verdicts"] == {}


@pytest.mark.unit
def test_without_the_review_bundle_it_publishes_no_verdicts(
    monkeypatch, tmp_path, sample_ui_comment_thread
):
    """The material cannot be written, so the session is never started."""
    monkeypatch.setattr(
        "titan_plugin_github.steps.code_review_steps.resolve_review_adapter",
        lambda ctx, step: (_adapter("{}"), None, False),
    )
    monkeypatch.setattr(
        "titan_plugin_github.steps.code_review_steps.announce_review_adapter",
        lambda ctx, adapter: None,
    )

    ctx = _ctx(tmp_path, [sample_ui_comment_thread])  # no change_manifest in context
    result = judge_pr_comments_step(ctx)

    assert isinstance(result, Success)
    assert result.metadata["comment_verdicts"] == {}


@pytest.mark.unit
def test_verdicts_are_published_by_comment_id_and_written_as_files(
    monkeypatch, tmp_path, sample_ui_comment_thread
):
    comment_id = sample_ui_comment_thread.main_comment.id
    answer = json.dumps(
        {
            "verdicts": [
                {
                    "comment_id": comment_id,
                    "verdict": "apply",
                    "reason": "the other caller is unguarded",
                    "files_affected": ["a.py"],
                    "callers_to_check": ["b.py"],
                    "proposed_fix": "guard it",
                },
                # An id nobody is judging: dropped rather than attached to a thread.
                {"comment_id": 999999, "verdict": "wrong", "reason": "x"},
            ]
        }
    )
    monkeypatch.setattr(
        "titan_plugin_github.steps.code_review_steps.resolve_review_adapter",
        lambda ctx, step: (_adapter(answer), None, False),
    )
    monkeypatch.setattr(
        "titan_plugin_github.steps.code_review_steps.announce_review_adapter",
        lambda ctx, adapter: None,
    )
    monkeypatch.setattr(pr_review_steps, "_write_judgement_material", lambda *a, **k: True)
    monkeypatch.setattr(pr_review_steps, "_material_root", lambda ctx, pr: tmp_path / "material")

    result = judge_pr_comments_step(_ctx(tmp_path, [sample_ui_comment_thread]))

    verdicts = result.metadata["comment_verdicts"]
    assert set(verdicts) == {comment_id}
    assert verdicts[comment_id].verdict == CommentVerdictType.APPLY
    assert verdicts[comment_id].callers_to_check == ["b.py"]

    path = result.metadata["verdict_files"][comment_id]
    assert "the other caller is unguarded" in open(path).read()


@pytest.mark.unit
def test_an_unreadable_answer_publishes_no_verdicts(
    monkeypatch, tmp_path, sample_ui_comment_thread
):
    monkeypatch.setattr(
        "titan_plugin_github.steps.code_review_steps.resolve_review_adapter",
        lambda ctx, step: (_adapter("I had a look and it all seems fine"), None, False),
    )
    monkeypatch.setattr(
        "titan_plugin_github.steps.code_review_steps.announce_review_adapter",
        lambda ctx, adapter: None,
    )
    monkeypatch.setattr(pr_review_steps, "_write_judgement_material", lambda *a, **k: True)
    monkeypatch.setattr(pr_review_steps, "_material_root", lambda ctx, pr: tmp_path / "material")

    result = judge_pr_comments_step(_ctx(tmp_path, [sample_ui_comment_thread]))

    assert isinstance(result, Success)
    assert result.metadata["comment_verdicts"] == {}


@pytest.mark.unit
def test_the_step_routes_under_the_respond_task():
    """O-002: the task the AI Routing screen offers now has a consumer."""
    assert judge_pr_comments_step.ai_policy.task == "respond_pr_comment"


@pytest.mark.unit
def test_material_is_pruned_to_the_most_recent_prs(tmp_path, monkeypatch):
    """Each directory holds a copy of every changed file, so it cannot grow forever."""
    base = tmp_path / ".titan" / "respond-comments"
    base.mkdir(parents=True)
    for n in range(8):
        d = base / f"repo-pr{n}"
        d.mkdir()
    monkeypatch.setattr(pr_review_steps.Path, "home", staticmethod(lambda: tmp_path))

    ctx = WorkflowContext()
    ctx.data["project_root"] = str(tmp_path / "repo")
    root = pr_review_steps._material_root(ctx, 42)

    assert root.name == "repo-pr42"
    assert len(list(base.iterdir())) == pr_review_steps.MATERIAL_KEPT_PRS


@pytest.mark.unit
def test_material_is_written_against_HEAD_not_the_review_worktree_ref(
    monkeypatch, tmp_path, sample_ui_comment_thread
):
    """The regression of run fe141507: this workflow has no worktree step, so
    `refs/titan/review/pr-N` does not exist and the merge base has to be taken from HEAD.
    Taking the review's default made the judging session start with no material at all,
    silently: the step reports "No verdicts" and the run carries on without it."""
    captured = {}

    def fake_write(ctx, root, manifest, diff_manager, threads, general, head_ref=None):
        captured["head_ref"] = head_ref
        # The real one lays the directory out; comments.md is written into it afterwards.
        (Path(root) / ".titan-review").mkdir(parents=True, exist_ok=True)
        return {"a.py": True}

    monkeypatch.setattr(
        "titan_plugin_github.steps.code_review_steps.write_review_material_at", fake_write
    )
    ctx = _ctx(tmp_path, [sample_ui_comment_thread])
    ctx.data["change_manifest"] = Mock()
    ctx.data["review_diff_manager"] = Mock()

    assert pr_review_steps._write_judgement_material(ctx, tmp_path / "m", [sample_ui_comment_thread])
    assert captured["head_ref"] == "HEAD"
