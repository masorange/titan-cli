from unittest.mock import Mock

from titan_cli.core.result import ClientError, ClientSuccess
from titan_cli.engine import WorkflowContext
from titan_cli.engine.results import Error, Exit, Success
from titan_cli.external_cli.adapters import HeadlessResponse
from titan_cli.external_cli.adapters.base import SupportedCLI
from titan_plugin_github.models.review_enums import FileReadMode, PRSizeClass, ReviewStrategyType
from titan_plugin_github.models.review_models import (
    ChangeManifest,
    FileContextEntry,
    FocusContextBatch,
    PullRequestManifest,
    ReferencedCommitContext,
    ReviewStrategy,
    ThreadReviewCandidate,
    ThreadReviewContext,
)
from titan_plugin_github.models.review_enums import FileChangeStatus
from titan_plugin_github.models.view import UIComment, UICommentThread, UIFileChange, UIPullRequest
import titan_plugin_github.steps.code_review_steps as code_review_steps
from titan_plugin_github.steps.code_review_steps import (
    ai_review_findings,
    ai_thread_resolution,
    build_thread_review_candidates,
    build_thread_review_contexts,
    fetch_pr_review_bundle,
    score_review_candidates,
)


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


def _make_pr(
    *, is_cross_repository: bool, author_name: str = "forkuser", head_repository_name: str = "some-repo"
) -> UIPullRequest:
    return UIPullRequest(
        number=223,
        title="Poeditor plugin implementation",
        body="Body",
        status_icon="🟢",
        state="OPEN",
        author_name=author_name,
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
        head_repository_owner="forkuser" if is_cross_repository else "base-org",
        head_repository_name=head_repository_name if is_cross_repository else None,
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
    ctx.github.get_current_user.return_value = ClientSuccess(data="reviewer", message="ok")
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


def test_fetch_pr_review_bundle_includes_current_github_user():
    pr = _make_pr(is_cross_repository=True)
    ctx = _make_context(pr)
    ctx.github.get_pr_diff.return_value = ClientSuccess(data="diff --git a/foo b/foo", message="ok")

    result = fetch_pr_review_bundle(ctx)

    assert isinstance(result, Success)
    assert result.metadata["review_current_user"] == "reviewer"
    ctx.github.get_current_user.assert_called_once_with()


def test_build_thread_review_candidates_filters_to_current_user_threads():
    ctx = WorkflowContext(secrets=Mock())
    ctx.textual = _FakeTextual()
    ctx.data["review_pr"] = _make_pr(is_cross_repository=False, author_name="author")
    ctx.data["review_current_user"] = "reviewer"
    ctx.data["review_threads"] = [
        _make_thread(reply_body="Fixed", path="src/main.py", line=42, body="Please fix this"),
        UICommentThread(
            thread_id="thread_456",
            main_comment=UIComment(
                id=20,
                body="Please fix this too",
                author_login="other-reviewer",
                author_name="Other Reviewer",
                formatted_date="",
                path="src/other.py",
                line=10,
            ),
            replies=[
                UIComment(
                    id=21,
                    body="Done",
                    author_login="gabrielglbh",
                    author_name="gabrielglbh",
                    formatted_date="",
                    path="src/other.py",
                    line=10,
                )
            ],
            is_resolved=False,
            is_outdated=False,
        ),
    ]

    result = build_thread_review_candidates(ctx)

    assert isinstance(result, Success)
    candidates = ctx.data["thread_review_candidates"]
    assert len(candidates) == 1
    assert candidates[0].main_comment_author == "reviewer"


def test_build_thread_review_candidates_errors_without_current_user():
    ctx = WorkflowContext(secrets=Mock())
    ctx.textual = _FakeTextual()
    ctx.data["review_pr"] = _make_pr(is_cross_repository=False)
    ctx.data["review_threads"] = []

    result = build_thread_review_candidates(ctx)

    assert isinstance(result, Error)
    assert result.message == "Current GitHub user not available"


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


def _make_thread(*, reply_body: str, path: str, line: int, body: str) -> UICommentThread:
    return UICommentThread(
        thread_id="thread_123",
        main_comment=UIComment(
            id=10,
            body=body,
            author_login="reviewer",
            author_name="Reviewer",
            formatted_date="",
            path=path,
            line=line,
            diff_hunk="@@ -541,3 +541,3 @@\n-fun ButtonDialog(dialogState: DialogState = rememberDialogState(false))\n+fun ButtonDialog(dialogState: DialogState)\n",
        ),
        replies=[
            UIComment(
                id=11,
                body=reply_body,
                author_login="author",
                author_name="Author",
                formatted_date="",
                path=path,
                line=line,
            )
        ],
        is_resolved=False,
        is_outdated=False,
    )


def test_build_thread_review_contexts_includes_referenced_commit_contexts():
    ctx = WorkflowContext(secrets=Mock())
    ctx.textual = _FakeTextual()
    ctx.github = Mock()
    ctx.data["thread_review_candidates"] = [
        ThreadReviewCandidate(
            thread_id="thread_123",
            path="freyja-core/src/main/kotlin/es/masorange/freyja/core/components/buttons/Buttons.kt",
            line=543,
            main_comment_body="Please fix the dialog state wiring",
            main_comment_author="reviewer",
            replies_count=1,
            last_reply_author="author",
            last_reply_body="Fixed in 343e2e9d7402d0afccfd35a9ecc8e6ea341031c6",
        )
    ]
    ctx.data["review_threads"] = [
        _make_thread(
            reply_body="Fixed in 343e2e9d7402d0afccfd35a9ecc8e6ea341031c6",
            path="freyja-core/src/main/kotlin/es/masorange/freyja/core/components/buttons/Buttons.kt",
            line=543,
            body="Please fix the dialog state wiring",
        )
    ]
    ctx.data["review_diff"] = (
        "diff --git a/freyja-core/src/main/kotlin/es/masorange/freyja/core/components/buttons/Buttons.kt "
        "b/freyja-core/src/main/kotlin/es/masorange/freyja/core/components/buttons/Buttons.kt\n"
        "@@ -541,3 +541,3 @@\n"
        "-fun ButtonDialog(dialogState: DialogState = rememberDialogState(false))\n"
        "+fun ButtonDialog(dialogState: DialogState)\n"
    )
    ctx.github.get_commit_review_context.return_value = ClientSuccess(
        data=ReferencedCommitContext(
            sha="343e2e9d7402d0afccfd35a9ecc8e6ea341031c6",
            abbreviated_sha="343e2e9",
            message="remove default state value",
            changed_files=["freyja-core/src/main/kotlin/.../BaseDialog.kt"],
            patch_excerpt="diff --git a/freyja-core/src/main/kotlin/.../BaseDialog.kt b/freyja-core/src/main/kotlin/.../BaseDialog.kt",
        ),
        message="ok",
    )

    result = build_thread_review_contexts(ctx)

    assert isinstance(result, Success)
    contexts = ctx.data["thread_review_contexts"]
    assert len(contexts) == 1
    assert contexts[0].referenced_commits[0].abbreviated_sha == "343e2e9"
    ctx.github.get_commit_review_context.assert_called_once_with(
        "343e2e9d7402d0afccfd35a9ecc8e6ea341031c6",
        repo_owner=None,
        repo_name=None,
        max_files=3,
        max_patch_chars=4000,
    )


def test_build_thread_review_contexts_resolves_referenced_commits_against_fork_head_repo():
    ctx = WorkflowContext(secrets=Mock())
    ctx.textual = _FakeTextual()
    ctx.github = Mock()
    ctx.data["review_pr"] = _make_pr(is_cross_repository=True, author_name="author", head_repository_name="fork-repo")
    ctx.data["thread_review_candidates"] = [
        ThreadReviewCandidate(
            thread_id="thread_123",
            path="freyja-core/src/main/kotlin/es/masorange/freyja/core/components/buttons/Buttons.kt",
            line=543,
            main_comment_body="Please fix the dialog state wiring",
            main_comment_author="reviewer",
            replies_count=1,
            last_reply_author="author",
            last_reply_body="Fixed in 343e2e9d7402d0afccfd35a9ecc8e6ea341031c6",
        )
    ]
    ctx.data["review_threads"] = [
        _make_thread(
            reply_body="Fixed in 343e2e9d7402d0afccfd35a9ecc8e6ea341031c6",
            path="freyja-core/src/main/kotlin/es/masorange/freyja/core/components/buttons/Buttons.kt",
            line=543,
            body="Please fix the dialog state wiring",
        )
    ]
    ctx.data["review_diff"] = (
        "diff --git a/freyja-core/src/main/kotlin/es/masorange/freyja/core/components/buttons/Buttons.kt "
        "b/freyja-core/src/main/kotlin/es/masorange/freyja/core/components/buttons/Buttons.kt\n"
        "@@ -541,3 +541,3 @@\n"
        "-fun ButtonDialog(dialogState: DialogState = rememberDialogState(false))\n"
        "+fun ButtonDialog(dialogState: DialogState)\n"
    )
    ctx.github.get_commit_review_context.return_value = ClientSuccess(
        data=ReferencedCommitContext(
            sha="343e2e9d7402d0afccfd35a9ecc8e6ea341031c6",
            abbreviated_sha="343e2e9",
            message="remove default state value",
            changed_files=["freyja-core/src/main/kotlin/.../BaseDialog.kt"],
            patch_excerpt="diff --git a/freyja-core/src/main/kotlin/.../BaseDialog.kt b/freyja-core/src/main/kotlin/.../BaseDialog.kt",
        ),
        message="ok",
    )

    result = build_thread_review_contexts(ctx)

    assert isinstance(result, Success)
    ctx.github.get_commit_review_context.assert_called_once_with(
        "343e2e9d7402d0afccfd35a9ecc8e6ea341031c6",
        repo_owner="forkuser",
        repo_name="fork-repo",
        max_files=3,
        max_patch_chars=4000,
    )


def test_build_thread_review_contexts_ignores_unavailable_referenced_commits():
    ctx = WorkflowContext(secrets=Mock())
    ctx.textual = _FakeTextual()
    ctx.github = Mock()
    ctx.data["thread_review_candidates"] = [
        ThreadReviewCandidate(
            thread_id="thread_123",
            path="src/main.py",
            line=42,
            main_comment_body="Please fix this",
            main_comment_author="reviewer",
            replies_count=1,
            last_reply_author="author",
            last_reply_body="Addressed in deadbee",
        )
    ]
    ctx.data["review_threads"] = [
        _make_thread(
            reply_body="Addressed in deadbee",
            path="src/main.py",
            line=42,
            body="Please fix this",
        )
    ]
    ctx.data["review_diff"] = "diff --git a/src/main.py b/src/main.py\n@@ -40,1 +40,1 @@\n-old\n+new\n"
    ctx.github.get_commit_review_context.return_value = ClientError(
        error_message="commit not found",
        error_code="API_ERROR",
    )

    result = build_thread_review_contexts(ctx)

    assert isinstance(result, Success)
    ctx.github.get_commit_review_context.assert_called_once_with(
        "deadbee",
        repo_owner=None,
        repo_name=None,
        max_files=3,
        max_patch_chars=4000,
    )
    contexts = ctx.data["thread_review_contexts"]
    assert contexts[0].referenced_commits == []


class _FakeFindingsAdapter:
    """Fake headless adapter recording every prompt it was asked to execute."""

    cli_name = SupportedCLI.CLAUDE

    def __init__(self):
        self.executed_prompts: list[str] = []

    def is_available(self) -> bool:
        return True

    def execute(self, prompt: str, cwd=None, timeout=None) -> HeadlessResponse:
        self.executed_prompts.append(prompt)
        return HeadlessResponse(stdout="[]", stderr="", exit_code=0)


def _make_findings_batch(batch_id: str, files_chars: dict[str, int]) -> FocusContextBatch:
    return FocusContextBatch(
        batch_id=batch_id,
        files_context={
            path: FileContextEntry(
                path=path,
                read_mode=FileReadMode.HUNKS_ONLY,
                hunks=["x" * chars],
                approximate_chars=chars,
            )
            for path, chars in files_chars.items()
        },
    )


def test_ai_review_findings_splits_oversized_batch_via_prompt_budget_manager(monkeypatch):
    """
    review-batching-003 wiring test: `ai_review_findings` must route batch
    fitting through `PromptBudgetManager.fit_batch_to_budget()` so an
    over-budget batch gets split and both halves are still sent to the CLI.
    """
    fake_adapter = _FakeFindingsAdapter()
    monkeypatch.setattr(code_review_steps, "_resolve_headless_adapter", lambda _pref: fake_adapter)

    ctx = WorkflowContext(secrets=Mock())
    ctx.textual = _FakeTextual()
    ctx.data["review_context_batches"] = [
        _make_findings_batch("batch_1", {"a.py": 3000, "b.py": 3000})
    ]
    ctx.data["review_strategy"] = ReviewStrategy(
        strategy=ReviewStrategyType.BATCHED_FINDINGS,
        size_class=PRSizeClass.SMALL,
        max_focus_files=10,
        max_prompt_chars=6000,
        max_comment_entries=5,
        batching_enabled=True,
    )
    ctx.data["cli_preference"] = "auto"
    ctx.data["project_root"] = "/tmp/project"

    result = ai_review_findings(ctx)

    assert isinstance(result, Success)
    # The oversized batch_1 must have been split into batch_1a/batch_1b, and
    # both halves sent to the adapter independently (2 CLI calls, not 1).
    assert len(fake_adapter.executed_prompts) == 2
    assert ctx.data["raw_findings"] == []
    assert ctx.data["ai_findings_failed"] is False


class _FakeFencedAdapter:
    """Fake headless adapter returning a markdown-fenced JSON array, once."""

    cli_name = SupportedCLI.CLAUDE

    def __init__(self, stdout: str):
        self._stdout = stdout

    def is_available(self) -> bool:
        return True

    def execute(self, prompt: str, cwd=None, timeout=None) -> HeadlessResponse:
        return HeadlessResponse(stdout=self._stdout, stderr="", exit_code=0)


def test_ai_review_findings_parses_markdown_fenced_response(monkeypatch):
    """review-batching-006: ai_review_findings must go through the centralized
    `extract_json_payload()` helper, which strips markdown fences — not a
    bespoke inline parser."""
    fake_adapter = _FakeFencedAdapter('```json\n[{"title": "Bug"}]\n```')
    monkeypatch.setattr(code_review_steps, "_resolve_headless_adapter", lambda _pref: fake_adapter)

    ctx = WorkflowContext(secrets=Mock())
    ctx.textual = _FakeTextual()
    ctx.data["review_context_batches"] = [_make_findings_batch("batch_1", {"a.py": 100})]
    ctx.data["review_strategy"] = ReviewStrategy(
        strategy=ReviewStrategyType.BATCHED_FINDINGS,
        size_class=PRSizeClass.SMALL,
        max_focus_files=10,
        max_prompt_chars=6000,
        max_comment_entries=5,
        batching_enabled=True,
    )
    ctx.data["cli_preference"] = "auto"
    ctx.data["project_root"] = "/tmp/project"

    result = ai_review_findings(ctx)

    assert isinstance(result, Success)
    assert ctx.data["raw_findings"] == [{"title": "Bug"}]
    assert ctx.data["ai_findings_failed"] is False


def test_ai_thread_resolution_parses_markdown_fenced_response(monkeypatch):
    """review-batching-006: ai_thread_resolution used to hand-roll its own fence
    stripping and JSON-slice extraction. It must now share the same
    `extract_json_payload()` helper as ai_review_findings/ai_review_plan."""
    fake_adapter = _FakeFencedAdapter('```json\n[{"thread_id": "t1", "decision": "resolved"}]\n```')
    monkeypatch.setattr(code_review_steps, "_resolve_headless_adapter", lambda _pref: fake_adapter)

    ctx = WorkflowContext(secrets=Mock())
    ctx.textual = _FakeTextual()
    ctx.data["thread_review_contexts"] = [
        ThreadReviewContext(
            thread_id="t1",
            comment_id=1,
            main_comment_body="Please fix this",
            main_comment_author="alex",
        )
    ]
    ctx.data["cli_preference"] = "auto"
    ctx.data["project_root"] = "/tmp/project"

    result = ai_thread_resolution(ctx)

    assert isinstance(result, Success)
    assert ctx.data["raw_thread_decisions"] == [{"thread_id": "t1", "decision": "resolved"}]


def test_ai_thread_resolution_falls_back_to_empty_decisions_on_parse_failure(monkeypatch):
    fake_adapter = _FakeFencedAdapter("I could not analyse these threads.")
    monkeypatch.setattr(code_review_steps, "_resolve_headless_adapter", lambda _pref: fake_adapter)

    ctx = WorkflowContext(secrets=Mock())
    ctx.textual = _FakeTextual()
    ctx.data["thread_review_contexts"] = [
        ThreadReviewContext(
            thread_id="t1",
            comment_id=1,
            main_comment_body="Please fix this",
            main_comment_author="alex",
        )
    ]
    ctx.data["cli_preference"] = "auto"
    ctx.data["project_root"] = "/tmp/project"

    result = ai_thread_resolution(ctx)

    assert isinstance(result, Success)
    assert ctx.data["raw_thread_decisions"] == []
