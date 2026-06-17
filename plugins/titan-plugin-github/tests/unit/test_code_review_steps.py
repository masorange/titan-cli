from unittest.mock import Mock

from titan_cli.external_cli.adapters.base import HeadlessResponse, SupportedCLI
from titan_cli.core.result import ClientSuccess
from titan_cli.engine import WorkflowContext
from titan_cli.engine.results import Exit, Success
from titan_plugin_github.managers.prompt_budget_manager import FitResult
from titan_plugin_github.models.review_models import ChangeManifest, FileContextEntry, FocusContextBatch, PullRequestManifest, ReviewStrategy
from titan_plugin_github.models.review_enums import FileChangeStatus, PRSizeClass, ReviewStrategyType
from titan_plugin_github.models.view import UIFileChange, UIPullRequest
from titan_plugin_github.steps import code_review_steps
from titan_plugin_github.steps.code_review_steps import ai_review_findings, fetch_pr_review_bundle, score_review_candidates


class _FakeTextual:
    def begin_step(self, _name):
        pass

    def end_step(self, _status):
        pass

    def dim_text(self, _text):
        pass

    def warning_text(self, _text):
        pass

    def error_text(self, _text):
        pass

    def success_text(self, _text):
        pass

    def text(self, _text):
        pass

    def bold_text(self, _text):
        pass

    def show_diff_stat(self, *_args, **_kwargs):
        pass

    class _Loading:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    def loading(self, _text):
        return self._Loading()


def _make_pr(*, is_cross_repository: bool) -> UIPullRequest:
    return UIPullRequest(
        number=223,
        title="Poeditor plugin implementation",
        body="Body",
        status_icon="🟢",
        state="OPEN",
        author_name="gabrielglbh",
        head_ref="poeditor-plugin",
        base_ref="master",
        branch_info="poeditor-plugin → master",
        stats="+10 -0",
        files_changed=2,
        is_mergeable=True,
        is_draft=False,
        review_summary="No reviews",
        labels=[],
        formatted_created_at="",
        formatted_updated_at="",
        is_cross_repository=is_cross_repository,
        head_repository_owner="gabrielglbh" if is_cross_repository else "masorange",
    )


def _make_file(path: str) -> UIFileChange:
    return UIFileChange(
        path=path,
        additions=10,
        deletions=0,
        status=FileChangeStatus.ADDED,
        status_icon="+",
    )


def _make_context(sample_pr: UIPullRequest) -> WorkflowContext:
    ctx = WorkflowContext(secrets=Mock())
    ctx.textual = _FakeTextual()
    ctx.github = Mock()
    ctx.git = Mock()
    ctx.data["review_pr_number"] = sample_pr.number
    ctx.github.get_pull_request.return_value = ClientSuccess(data=sample_pr, message="ok")
    ctx.github.get_pr_files_with_stats.return_value = ClientSuccess(
        data=[_make_file("plugins/titan-plugin-poeditor/plugin.py")],
        message="ok",
    )
    ctx.github.get_pr_commit_sha.return_value = ClientSuccess(data="abc123", message="ok")
    ctx.github.get_pr_review_threads.return_value = ClientSuccess(data=[], message="ok")
    ctx.github.get_pr_general_comments.return_value = ClientSuccess(data=[], message="ok")
    ctx.github.get_pr_template.return_value = None
    return ctx


def test_fetch_pr_review_bundle_uses_github_diff_for_cross_repo_pr():
    pr = _make_pr(is_cross_repository=True)
    ctx = _make_context(pr)
    ctx.github.get_pr_diff.return_value = ClientSuccess(data="diff --git a/foo b/foo", message="ok")

    result = fetch_pr_review_bundle(ctx)

    assert isinstance(result, Success)
    assert result.metadata["review_diff"] == "diff --git a/foo b/foo"
    ctx.github.get_pr_diff.assert_called_once_with(223)
    ctx.git.get_branch_diff.assert_not_called()


def test_fetch_pr_review_bundle_falls_back_to_github_diff_when_git_diff_empty():
    pr = _make_pr(is_cross_repository=False)
    ctx = _make_context(pr)
    ctx.git.fetch.return_value = ClientSuccess(data=None, message="ok")
    ctx.git.get_branch_diff.return_value = ClientSuccess(data="", message="empty")
    ctx.github.get_pr_diff.return_value = ClientSuccess(data="diff --git a/foo b/foo", message="ok")

    result = fetch_pr_review_bundle(ctx)

    assert isinstance(result, Success)
    assert result.metadata["review_diff"] == "diff --git a/foo b/foo"
    ctx.git.get_branch_diff.assert_called_once()
    ctx.github.get_pr_diff.assert_called_once_with(223)


def test_fetch_pr_review_bundle_falls_back_to_github_diff_when_git_diff_fails():
    pr = _make_pr(is_cross_repository=False)
    ctx = _make_context(pr)
    ctx.git.fetch.return_value = ClientSuccess(data=None, message="ok")
    from titan_cli.core.result import ClientError

    ctx.git.get_branch_diff.return_value = ClientError(error_message="unknown revision")
    ctx.github.get_pr_diff.return_value = ClientSuccess(data="diff --git a/foo b/foo", message="ok")

    result = fetch_pr_review_bundle(ctx)

    assert isinstance(result, Success)
    assert result.metadata["review_diff"] == "diff --git a/foo b/foo"
    ctx.github.get_pr_diff.assert_called_once_with(223)


def test_fetch_pr_review_bundle_exits_when_pr_has_no_files_and_no_diff():
    pr = _make_pr(is_cross_repository=True)
    ctx = WorkflowContext(secrets=Mock())
    ctx.textual = _FakeTextual()
    ctx.github = Mock()
    ctx.git = Mock()
    ctx.data["review_pr_number"] = pr.number
    ctx.github.get_pull_request.return_value = ClientSuccess(data=pr, message="ok")
    ctx.github.get_pr_files_with_stats.return_value = ClientSuccess(data=[], message="ok")
    ctx.github.get_pr_commit_sha.return_value = ClientSuccess(data="abc123", message="ok")
    ctx.github.get_pr_diff.return_value = ClientSuccess(data="", message="empty")

    result = fetch_pr_review_bundle(ctx)

    assert isinstance(result, Exit)
    assert result.message == "Empty PR diff"


def test_score_review_candidates_exits_when_no_reviewable_candidates_remain():
    ctx = WorkflowContext(secrets=Mock())
    ctx.textual = _FakeTextual()
    ctx.data["change_manifest"] = ChangeManifest(
        pr=PullRequestManifest(
            number=215,
            title="docs-only cleanup",
            base="master",
            head="cleanup",
            author="alex",
            description="Body",
        ),
        files=[
            MockChangedFile(
                path="docs/readme.md",
                status="modified",
                additions=1,
                deletions=0,
                is_docs=True,
            )
        ],
        total_additions=1,
        total_deletions=0,
    )

    result = score_review_candidates(ctx)

    assert isinstance(result, Exit)
    assert result.message == "No reviewable candidates after exclusions"


def MockChangedFile(**kwargs):
    from titan_plugin_github.models.review_models import ChangedFileEntry

    return ChangedFileEntry(**kwargs)


def test_ai_review_findings_uses_prompt_budget_manager(monkeypatch):
    ctx = WorkflowContext(secrets=Mock())
    ctx.textual = _FakeTextual()
    ctx.data["review_context_batches"] = [
        FocusContextBatch(
            batch_id="batch_1",
            files_context={"src/foo.py": FileContextEntry(path="src/foo.py")},
        )
    ]
    ctx.data["review_strategy"] = ReviewStrategy(
        strategy=ReviewStrategyType.DIRECT_FINDINGS,
        size_class=PRSizeClass.SMALL,
        max_focus_files=4,
        max_prompt_chars=22000,
        max_comment_entries=8,
    )
    ctx.data["cli_preference"] = "claude"
    ctx.data["project_root"] = "/tmp/repo"

    called = {"fit": 0}

    def fake_fit(self, batch, prompt_parts, budget_chars):
        called["fit"] += 1
        assert batch.batch_id == "batch_1"
        assert prompt_parts["prompt"] == "[]"
        assert budget_chars == 22000
        fitted = batch.model_copy(update={"prompt_actual_chars": 2})
        return FitResult(batches=[fitted], changed=False)

    class _FakeAdapter:
        cli_name = SupportedCLI.CLAUDE

        def execute(self, prompt, cwd=None, timeout=60):
            assert prompt == "[]"
            assert cwd == "/tmp/repo"
            return HeadlessResponse(stdout="[]", stderr="", exit_code=0)

    monkeypatch.setattr(code_review_steps, "_resolve_headless_adapter", lambda _cli: _FakeAdapter())
    monkeypatch.setattr(
        "titan_plugin_github.operations.findings_operations.build_findings_prompt_parts",
        lambda _batch: {"prompt": "[]", "pr_context": "", "comments": "", "review_axes": "", "files_context": "", "related_context": "", "instructions": "", "schema": ""},
    )
    monkeypatch.setattr(
        "titan_plugin_github.operations.findings_operations.summarize_findings_prompt_parts",
        lambda _parts: {},
    )
    monkeypatch.setattr("titan_plugin_github.managers.prompt_budget_manager.PromptBudgetManager.fit_findings_batch_to_budget", fake_fit)

    result = ai_review_findings(ctx)

    assert isinstance(result, Success)
    assert called["fit"] == 1
    assert ctx.data["raw_findings"] == []
