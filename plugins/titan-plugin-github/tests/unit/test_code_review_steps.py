import threading
from unittest.mock import Mock

from titan_cli.core.result import ClientError, ClientSuccess
from titan_cli.engine import WorkflowContext
from titan_cli.engine.results import Error, Exit, Skip, Success
from titan_cli.external_cli.adapters import HeadlessResponse
from titan_cli.external_cli.adapters.base import SupportedCLI
from titan_plugin_github.models.review_enums import FileReadMode
from titan_plugin_github.models.review_models import (
    ChangeManifest,
    PullRequestManifest,
    FileContextEntry,
    FocusContextBatch,
    ReferencedCommitContext,
    ReviewBudget,
    ThreadReviewCandidate,
    ThreadReviewContext,
)
from titan_plugin_github.models.review_enums import FileChangeStatus
from titan_plugin_github.models.review_profile_models import ReviewProfile
from titan_plugin_github.models.view import UIComment, UICommentThread, UIFileChange, UIPullRequest
import titan_plugin_github.steps.code_review_steps as code_review_steps
from titan_plugin_github.steps.code_review_steps import (
    ai_review_findings,
    ai_thread_resolution,
    build_thread_review_candidates,
    build_thread_review_contexts,
    fetch_pr_review_bundle,
)


class _FakeTextual:
    def __init__(self):
        self.warnings: list[str] = []

    def begin_step(self, _name):
        pass

    def end_step(self, _status):
        pass

    def dim_text(self, _text):
        pass

    def warning_text(self, text):
        self.warnings.append(text)

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

    def ai_chip(self, _text):
        pass


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
    ctx = WorkflowContext()
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


def test_fetch_pr_review_bundle_uses_local_u3_diff_when_github_diff_unavailable():
    """GitHub refuses diffs over 20k lines (406). The publishable-lines source then
    comes from a local 3-context diff instead of degrading to added-lines-only."""
    pr = _make_pr(is_cross_repository=False)
    ctx = _make_context(pr)
    from titan_cli.core.result import ClientError

    u20_diff = "diff --git a/foo b/foo\n--- a/foo\n+++ b/foo\n@@ -1,1 +1,2 @@\n line1\n+added\n"
    u3_diff = "diff --git a/foo b/foo\n--- a/foo\n+++ b/foo\n@@ -1,1 +1,2 @@\n line1\n+added\n"
    ctx.git.fetch.return_value = ClientSuccess(data=None, message="ok")
    ctx.git.get_branch_diff.side_effect = [
        ClientSuccess(data=u20_diff, message="ok"),
        ClientSuccess(data=u3_diff, message="ok"),
    ]
    ctx.github.get_pr_diff.return_value = ClientError(
        error_message="HTTP 406: diff exceeded the maximum number of lines (20000)"
    )

    result = fetch_pr_review_bundle(ctx)

    assert isinstance(result, Success)
    assert result.metadata["review_diff_manager"].has_github_diff is True
    # Second get_branch_diff call is the publish-validation source, at 3 context lines.
    validation_call = ctx.git.get_branch_diff.call_args_list[1]
    assert validation_call.kwargs.get("context_lines") == 3


def test_fetch_pr_review_bundle_exits_when_pr_has_no_files_and_no_diff():
    pr = _make_pr(is_cross_repository=True)
    ctx = WorkflowContext()
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
    ctx = WorkflowContext()
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
    ctx = WorkflowContext()
    ctx.textual = _FakeTextual()
    ctx.data["review_pr"] = _make_pr(is_cross_repository=False)
    ctx.data["review_threads"] = []

    result = build_thread_review_candidates(ctx)

    assert isinstance(result, Error)
    assert result.message == "Current GitHub user not available"


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
    ctx = WorkflowContext()
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
    ctx = WorkflowContext()
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
    ctx = WorkflowContext()
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

    supports_structured_output = False
    supports_tool_restriction = False
    supports_effort_control = False

    def is_available(self) -> bool:
        return True

    def execute(self, prompt: str, cwd=None, timeout=None, json_schema=None, disallowed_tools=None, effort=None) -> HeadlessResponse:
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

    ctx = WorkflowContext()
    ctx.textual = _FakeTextual()
    ctx.data["review_context_batches"] = [
        _make_findings_batch("batch_1", {"a.py": 3000, "b.py": 3000})
    ]
    ctx.data["review_budget"] = ReviewBudget(
        deep_max_prompt_chars=6000,
        triage_max_prompt_chars=6000,
        max_comment_entries=5,
        deep_timeout_base_seconds=300,
        deep_timeout_per_file_seconds=120,
        deep_timeout_max_seconds=1500,
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
    supports_structured_output = False
    supports_tool_restriction = False
    supports_effort_control = False

    def __init__(self, stdout: str):
        self._stdout = stdout

    def is_available(self) -> bool:
        return True

    def execute(self, prompt: str, cwd=None, timeout=None, json_schema=None, disallowed_tools=None, effort=None) -> HeadlessResponse:
        return HeadlessResponse(stdout=self._stdout, stderr="", exit_code=0)


def test_ai_review_findings_parses_markdown_fenced_response(monkeypatch):
    """review-batching-006: ai_review_findings must go through the centralized
    `extract_json_payload()` helper, which strips markdown fences — not a
    bespoke inline parser."""
    fake_adapter = _FakeFencedAdapter('```json\n[{"title": "Bug"}]\n```')
    monkeypatch.setattr(code_review_steps, "_resolve_headless_adapter", lambda _pref: fake_adapter)

    ctx = WorkflowContext()
    ctx.textual = _FakeTextual()
    ctx.data["review_context_batches"] = [_make_findings_batch("batch_1", {"a.py": 100})]
    ctx.data["review_budget"] = ReviewBudget(
        deep_max_prompt_chars=6000,
        triage_max_prompt_chars=6000,
        max_comment_entries=5,
        deep_timeout_base_seconds=300,
        deep_timeout_per_file_seconds=120,
        deep_timeout_max_seconds=1500,
    )
    ctx.data["cli_preference"] = "auto"
    ctx.data["project_root"] = "/tmp/project"

    result = ai_review_findings(ctx)

    assert isinstance(result, Success)
    assert ctx.data["raw_findings"] == [{"title": "Bug"}]
    assert ctx.data["ai_findings_failed"] is False


class _FakeSequentialAdapter:
    """Fake headless adapter returning one canned stdout per call, in order."""

    cli_name = SupportedCLI.CLAUDE
    supports_structured_output = False
    supports_tool_restriction = False
    supports_effort_control = False

    def __init__(self, stdouts: list[str]):
        self._stdouts = list(stdouts)
        self.calls: list[dict] = []

    def is_available(self) -> bool:
        return True

    def execute(self, prompt: str, cwd=None, timeout=None, json_schema=None, disallowed_tools=None, effort=None) -> HeadlessResponse:
        self.calls.append(
            {"prompt": prompt, "cwd": cwd, "timeout": timeout, "disallowed_tools": disallowed_tools, "effort": effort}
        )
        stdout = self._stdouts[len(self.calls) - 1]
        return HeadlessResponse(stdout=stdout, stderr="", exit_code=0)


def test_ai_review_findings_recovers_via_reformat_retry(monkeypatch):
    """review-batching-007: when the model returns prose instead of JSON
    (exit_code 0), ai_review_findings must retry once, asking the same CLI to
    reformat its own previous output, using a short timeout distinct from the
    300s analysis timeout — and recover the findings if the retry succeeds."""
    fake_adapter = _FakeSequentialAdapter(
        ["Reported one finding: fix the null check.", '```json\n[{"title": "Bug"}]\n```']
    )
    monkeypatch.setattr(code_review_steps, "_resolve_headless_adapter", lambda _pref: fake_adapter)

    ctx = WorkflowContext()
    ctx.textual = _FakeTextual()
    ctx.data["review_context_batches"] = [_make_findings_batch("batch_1", {"a.py": 100})]
    ctx.data["review_budget"] = ReviewBudget(
        deep_max_prompt_chars=6000,
        triage_max_prompt_chars=6000,
        max_comment_entries=5,
        deep_timeout_base_seconds=300,
        deep_timeout_per_file_seconds=120,
        deep_timeout_max_seconds=1500,
    )
    ctx.data["cli_preference"] = "auto"
    ctx.data["project_root"] = "/tmp/project"

    result = ai_review_findings(ctx)

    assert isinstance(result, Success)
    assert ctx.data["raw_findings"] == [{"title": "Bug"}]
    assert ctx.data["ai_findings_failed"] is False
    assert len(fake_adapter.calls) == 2
    assert fake_adapter.calls[1]["timeout"] == 45
    assert fake_adapter.calls[1]["timeout"] != fake_adapter.calls[0]["timeout"]


def test_ai_review_findings_marks_batch_failed_when_reformat_retry_also_fails(monkeypatch):
    fake_adapter = _FakeSequentialAdapter(
        ["Reported one finding: fix the null check.", "Still no JSON here, sorry."]
    )
    monkeypatch.setattr(code_review_steps, "_resolve_headless_adapter", lambda _pref: fake_adapter)

    ctx = WorkflowContext()
    ctx.textual = _FakeTextual()
    ctx.data["review_context_batches"] = [_make_findings_batch("batch_1", {"a.py": 100})]
    ctx.data["review_budget"] = ReviewBudget(
        deep_max_prompt_chars=6000,
        triage_max_prompt_chars=6000,
        max_comment_entries=5,
        deep_timeout_base_seconds=300,
        deep_timeout_per_file_seconds=120,
        deep_timeout_max_seconds=1500,
    )
    ctx.data["cli_preference"] = "auto"
    ctx.data["project_root"] = "/tmp/project"

    result = ai_review_findings(ctx)

    # The only batch failed, so the whole step must fail visibly (0/1 produced output).
    assert isinstance(result, Error)
    assert len(fake_adapter.calls) == 2
    assert ctx.data["ai_findings_failed"] is True
    assert ctx.data["raw_findings"] == []


def test_ai_review_findings_partial_batch_failure_still_succeeds_with_flag(monkeypatch):
    """One batch fails parse (main + retry), the other returns findings: the step
    succeeds but ai_findings_failed must be True so the outcome isn't presented
    as a fully clean review."""
    from titan_plugin_github.models.review_profile_models import ReviewProfile

    fake_adapter = _FakeSequentialAdapter(
        [
            "Reported one finding: fix the null check.",  # batch_1 main call (prose)
            "Still no JSON here, sorry.",  # batch_1 reformat retry
            '[{"title": "Bug"}]',  # batch_2 main call
        ]
    )
    monkeypatch.setattr(code_review_steps, "_resolve_headless_adapter", lambda _pref: fake_adapter)

    ctx = WorkflowContext()
    ctx.textual = _FakeTextual()
    # The canned-stdout sequence assumes batch order — pin the pool to 1.
    ctx.data["review_profile"] = ReviewProfile()
    ctx.data["review_context_batches"] = [
        _make_findings_batch("batch_1", {"a.py": 100}),
        _make_findings_batch("batch_2", {"b.py": 100}),
    ]
    ctx.data["review_budget"] = ReviewBudget(
        deep_max_prompt_chars=6000,
        triage_max_prompt_chars=6000,
        max_comment_entries=5,
        deep_timeout_base_seconds=300,
        deep_timeout_per_file_seconds=120,
        deep_timeout_max_seconds=1500,
    )
    ctx.data["cli_preference"] = "auto"
    ctx.data["project_root"] = "/tmp/project"

    result = ai_review_findings(ctx)

    assert isinstance(result, Success)
    assert ctx.data["raw_findings"] == [{"title": "Bug"}]
    assert ctx.data["ai_findings_failed"] is True


class _FakeFailingCLIAdapter:
    """Fake headless adapter whose every call fails with a non-zero exit code."""

    cli_name = SupportedCLI.CLAUDE
    supports_structured_output = False
    supports_tool_restriction = False
    supports_effort_control = False

    def __init__(self, exit_code: int = 1):
        self._exit_code = exit_code
        self.calls = 0

    def is_available(self) -> bool:
        return True

    def execute(self, prompt: str, cwd=None, timeout=None, json_schema=None, disallowed_tools=None, effort=None) -> HeadlessResponse:
        self.calls += 1
        return HeadlessResponse(stdout="", stderr="credit balance too low", exit_code=self._exit_code)


def test_ai_review_findings_returns_error_when_all_batches_fail(monkeypatch):
    """review-quality-005: when every batch fails (e.g. headless CLI without credits,
    observed live 2026-07-31), the step must NOT report plain Success — a total AI
    failure was indistinguishable from a clean review. raw_findings stays published
    (empty) so downstream steps and worktree cleanup still run via on_error: continue."""
    fake_adapter = _FakeFailingCLIAdapter(exit_code=1)
    monkeypatch.setattr(code_review_steps, "_resolve_headless_adapter", lambda _pref: fake_adapter)

    ctx = WorkflowContext()
    ctx.textual = _FakeTextual()
    ctx.data["review_context_batches"] = [
        _make_findings_batch("batch_1", {"a.py": 100}),
        _make_findings_batch("batch_2", {"b.py": 100}),
    ]
    ctx.data["review_budget"] = ReviewBudget(
        deep_max_prompt_chars=6000,
        triage_max_prompt_chars=6000,
        max_comment_entries=5,
        deep_timeout_base_seconds=300,
        deep_timeout_per_file_seconds=120,
        deep_timeout_max_seconds=1500,
    )
    ctx.data["cli_preference"] = "auto"
    ctx.data["project_root"] = "/tmp/project"

    result = ai_review_findings(ctx)

    assert isinstance(result, Error)
    assert "0/2" in result.message
    assert fake_adapter.calls == 2
    assert ctx.data["raw_findings"] == []
    assert ctx.data["ai_findings_failed"] is True


class _FakeStructuredSequentialAdapter:
    """Fake structured-output adapter returning one canned stdout per call, in order."""

    cli_name = SupportedCLI.CLAUDE
    supports_structured_output = True
    supports_tool_restriction = True
    supports_effort_control = True

    def __init__(self, stdouts: list[str]):
        self._stdouts = list(stdouts)
        self.calls: list[dict] = []

    def is_available(self) -> bool:
        return True

    def execute(self, prompt: str, cwd=None, timeout=None, json_schema=None, disallowed_tools=None, effort=None) -> HeadlessResponse:
        self.calls.append({"prompt": prompt, "timeout": timeout, "json_schema": json_schema})
        stdout = self._stdouts[len(self.calls) - 1]
        return HeadlessResponse(stdout=stdout, stderr="", exit_code=0)


def test_ai_review_findings_non_list_payload_goes_through_reformat_retry(monkeypatch):
    """review-quality-005: a structured success whose findings payload isn't a list
    (e.g. a dict) used to hit `case ClientSuccess(): pass` and vanish — no failure
    flag, no batch result rendered. It must go through the reformat-retry path and
    recover when the retry returns a proper list."""
    fake_adapter = _FakeStructuredSequentialAdapter(
        [
            '{"findings": {"title": "Bug"}}',  # main call: dict payload, not a list
            '{"findings": [{"title": "Bug"}]}',  # reformat retry: proper list
        ]
    )
    monkeypatch.setattr(code_review_steps, "_resolve_headless_adapter", lambda _pref: fake_adapter)

    ctx = WorkflowContext()
    ctx.textual = _FakeTextual()
    ctx.data["review_context_batches"] = [_make_findings_batch("batch_1", {"a.py": 100})]
    ctx.data["review_budget"] = ReviewBudget(
        deep_max_prompt_chars=6000,
        triage_max_prompt_chars=6000,
        max_comment_entries=5,
        deep_timeout_base_seconds=300,
        deep_timeout_per_file_seconds=120,
        deep_timeout_max_seconds=1500,
    )
    ctx.data["cli_preference"] = "auto"
    ctx.data["project_root"] = "/tmp/project"

    result = ai_review_findings(ctx)

    assert isinstance(result, Success)
    assert len(fake_adapter.calls) == 2
    assert ctx.data["raw_findings"] == [{"title": "Bug"}]
    assert ctx.data["ai_findings_failed"] is False


def test_ai_review_findings_non_list_payload_marks_failed_when_retry_also_non_list(monkeypatch):
    fake_adapter = _FakeStructuredSequentialAdapter(
        [
            '{"findings": {"title": "Bug"}}',  # main call: dict payload
            '{"findings": {"title": "Bug"}}',  # retry: still a dict
        ]
    )
    monkeypatch.setattr(code_review_steps, "_resolve_headless_adapter", lambda _pref: fake_adapter)

    ctx = WorkflowContext()
    ctx.textual = _FakeTextual()
    ctx.data["review_context_batches"] = [_make_findings_batch("batch_1", {"a.py": 100})]
    ctx.data["review_budget"] = ReviewBudget(
        deep_max_prompt_chars=6000,
        triage_max_prompt_chars=6000,
        max_comment_entries=5,
        deep_timeout_base_seconds=300,
        deep_timeout_per_file_seconds=120,
        deep_timeout_max_seconds=1500,
    )
    ctx.data["cli_preference"] = "auto"
    ctx.data["project_root"] = "/tmp/project"

    result = ai_review_findings(ctx)

    # Single batch, non-list payload twice: batch failed, so 0/1 → step fails visibly.
    assert isinstance(result, Error)
    assert len(fake_adapter.calls) == 2
    assert ctx.data["ai_findings_failed"] is True
    assert ctx.data["raw_findings"] == []


class _FakeStructuredOutputAdapter:
    """Fake adapter simulating a CLI that supports --json-schema (like Claude)."""

    cli_name = SupportedCLI.CLAUDE
    supports_structured_output = True
    supports_tool_restriction = True
    supports_effort_control = True

    def __init__(self, stdout: str):
        self._stdout = stdout
        self.calls: list[dict] = []

    def is_available(self) -> bool:
        return True

    def execute(self, prompt: str, cwd=None, timeout=None, json_schema=None, disallowed_tools=None, effort=None) -> HeadlessResponse:
        self.calls.append(
            {
                "prompt": prompt,
                "cwd": cwd,
                "timeout": timeout,
                "json_schema": json_schema,
                "disallowed_tools": disallowed_tools,
                "effort": effort,
            }
        )
        return HeadlessResponse(stdout=self._stdout, stderr="", exit_code=0)


def test_ai_review_findings_uses_structured_output_when_supported(monkeypatch):
    """review-batching-008: when the adapter supports structured output, ai_review_findings
    must request it (json_schema kwarg) and unwrap the {"findings": [...]} envelope,
    instead of parsing a bare JSON array out of free text."""
    fake_adapter = _FakeStructuredOutputAdapter('{"findings": [{"title": "Bug"}]}')
    monkeypatch.setattr(code_review_steps, "_resolve_headless_adapter", lambda _pref: fake_adapter)

    ctx = WorkflowContext()
    ctx.textual = _FakeTextual()
    ctx.data["review_context_batches"] = [_make_findings_batch("batch_1", {"a.py": 100})]
    ctx.data["review_budget"] = ReviewBudget(
        deep_max_prompt_chars=6000,
        triage_max_prompt_chars=6000,
        max_comment_entries=5,
        deep_timeout_base_seconds=300,
        deep_timeout_per_file_seconds=120,
        deep_timeout_max_seconds=1500,
    )
    ctx.data["cli_preference"] = "auto"
    ctx.data["project_root"] = "/tmp/project"

    result = ai_review_findings(ctx)

    assert isinstance(result, Success)
    assert ctx.data["raw_findings"] == [{"title": "Bug"}]
    assert ctx.data["ai_findings_failed"] is False
    assert fake_adapter.calls[0]["json_schema"] is not None
    assert fake_adapter.calls[0]["json_schema"]["required"] == ["findings", "dismissed"]


def test_ai_review_findings_structured_output_retry_also_requests_schema(monkeypatch):
    """If the model doesn't call the structured-output tool on the first try (rare), the
    reformat retry must still request structured output — not silently downgrade to
    free-text parsing."""
    fake_adapter = _FakeStructuredOutputAdapter("I won't call that tool.")
    monkeypatch.setattr(code_review_steps, "_resolve_headless_adapter", lambda _pref: fake_adapter)

    ctx = WorkflowContext()
    ctx.textual = _FakeTextual()
    ctx.data["review_context_batches"] = [_make_findings_batch("batch_1", {"a.py": 100})]
    ctx.data["review_budget"] = ReviewBudget(
        deep_max_prompt_chars=6000,
        triage_max_prompt_chars=6000,
        max_comment_entries=5,
        deep_timeout_base_seconds=300,
        deep_timeout_per_file_seconds=120,
        deep_timeout_max_seconds=1500,
    )
    ctx.data["cli_preference"] = "auto"
    ctx.data["project_root"] = "/tmp/project"

    result = ai_review_findings(ctx)

    # The only batch failed even after the retry, so the step fails (0/1 produced output).
    assert isinstance(result, Error)
    assert len(fake_adapter.calls) == 2
    assert fake_adapter.calls[1]["json_schema"] is not None
    assert ctx.data["ai_findings_failed"] is True


def test_ai_review_findings_restricts_tools_when_supported(monkeypatch):
    """O-003/D-011 fix: when the adapter supports tool restriction, ai_review_findings must
    deny Bash (and the other unneeded tools) so the CLI can't explore far beyond the batch's
    worktree_reference files — Read/Grep/Glob stay implicitly available since they're not
    in the denylist."""
    from titan_plugin_github.operations.findings_operations import FINDINGS_DISALLOWED_TOOLS

    fake_adapter = _FakeStructuredOutputAdapter('{"findings": [{"title": "Bug"}]}')
    monkeypatch.setattr(code_review_steps, "_resolve_headless_adapter", lambda _pref: fake_adapter)

    ctx = WorkflowContext()
    ctx.textual = _FakeTextual()
    ctx.data["review_context_batches"] = [_make_findings_batch("batch_1", {"a.py": 100})]
    ctx.data["review_budget"] = ReviewBudget(
        deep_max_prompt_chars=6000,
        triage_max_prompt_chars=6000,
        max_comment_entries=5,
        deep_timeout_base_seconds=300,
        deep_timeout_per_file_seconds=120,
        deep_timeout_max_seconds=1500,
    )
    ctx.data["cli_preference"] = "auto"
    ctx.data["project_root"] = "/tmp/project"

    result = ai_review_findings(ctx)

    assert isinstance(result, Success)
    assert fake_adapter.calls[0]["disallowed_tools"] == list(FINDINGS_DISALLOWED_TOOLS)


def test_ai_review_findings_omits_disallowed_tools_when_unsupported(monkeypatch):
    """Adapters without tool-restriction support (Codex, Gemini) must not receive a
    disallowed_tools list — the step must not assume the capability is universal."""
    fake_adapter = _FakeSequentialAdapter(['[{"title": "Bug"}]'])
    monkeypatch.setattr(code_review_steps, "_resolve_headless_adapter", lambda _pref: fake_adapter)

    ctx = WorkflowContext()
    ctx.textual = _FakeTextual()
    ctx.data["review_context_batches"] = [_make_findings_batch("batch_1", {"a.py": 100})]
    ctx.data["review_budget"] = ReviewBudget(
        deep_max_prompt_chars=6000,
        triage_max_prompt_chars=6000,
        max_comment_entries=5,
        deep_timeout_base_seconds=300,
        deep_timeout_per_file_seconds=120,
        deep_timeout_max_seconds=1500,
    )
    ctx.data["cli_preference"] = "auto"
    ctx.data["project_root"] = "/tmp/project"

    result = ai_review_findings(ctx)

    assert isinstance(result, Success)
    assert fake_adapter.calls[0]["disallowed_tools"] is None


def test_ai_review_findings_reformat_retry_also_restricts_tools(monkeypatch):
    """The reformat retry reuses the same adapter for a lighter-weight call with no
    exploration need at all — it must still receive the same tool restriction."""
    from titan_plugin_github.operations.findings_operations import FINDINGS_DISALLOWED_TOOLS

    fake_adapter = _FakeStructuredOutputAdapter("I won't call that tool.")
    monkeypatch.setattr(code_review_steps, "_resolve_headless_adapter", lambda _pref: fake_adapter)

    ctx = WorkflowContext()
    ctx.textual = _FakeTextual()
    ctx.data["review_context_batches"] = [_make_findings_batch("batch_1", {"a.py": 100})]
    ctx.data["review_budget"] = ReviewBudget(
        deep_max_prompt_chars=6000,
        triage_max_prompt_chars=6000,
        max_comment_entries=5,
        deep_timeout_base_seconds=300,
        deep_timeout_per_file_seconds=120,
        deep_timeout_max_seconds=1500,
    )
    ctx.data["cli_preference"] = "auto"
    ctx.data["project_root"] = "/tmp/project"

    result = ai_review_findings(ctx)

    # The only batch failed even after the retry, so the step fails (0/1 produced output).
    assert isinstance(result, Error)
    assert len(fake_adapter.calls) == 2
    assert fake_adapter.calls[1]["disallowed_tools"] == list(FINDINGS_DISALLOWED_TOOLS)


def _make_worktree_reference_batch(batch_id: str, path: str) -> FocusContextBatch:
    return FocusContextBatch(
        batch_id=batch_id,
        files_context={
            path: FileContextEntry(
                path=path,
                read_mode=FileReadMode.WORKTREE_REFERENCE,
                worktree_reference=True,
                review_hint="Read this file from the worktree.",
                approximate_chars=100,
            )
        },
    )


def test_ai_review_findings_sets_effort_for_worktree_reference_batch(monkeypatch):
    """A batch that reads files from the worktree gets an explicit effort, not the CLI's
    default, and ai_review_findings must pass it through.

    The VALUE moved from medium to high once the deep tier became one session: measured on
    PR 251, medium found 5 findings in 4 files for $2.1809 and high found 7 in 5 for
    $2.5215. What the test pins is that the constant reaches the adapter, not which value
    it holds."""
    from titan_plugin_github.operations.findings_operations import FINDINGS_WORKTREE_REFERENCE_EFFORT

    fake_adapter = _FakeStructuredOutputAdapter('{"findings": []}')
    monkeypatch.setattr(code_review_steps, "_resolve_headless_adapter", lambda _pref: fake_adapter)

    ctx = WorkflowContext()
    ctx.textual = _FakeTextual()
    ctx.data["review_context_batches"] = [_make_worktree_reference_batch("batch_1", "HomeScreen.kt")]
    ctx.data["review_budget"] = ReviewBudget(
        deep_max_prompt_chars=6000,
        triage_max_prompt_chars=6000,
        max_comment_entries=5,
        deep_timeout_base_seconds=300,
        deep_timeout_per_file_seconds=120,
        deep_timeout_max_seconds=1500,
    )
    ctx.data["cli_preference"] = "auto"
    ctx.data["project_root"] = "/tmp/project"

    result = ai_review_findings(ctx)

    assert isinstance(result, Success)
    assert fake_adapter.calls[0]["effort"] == FINDINGS_WORKTREE_REFERENCE_EFFORT


def test_ai_review_findings_omits_effort_when_no_worktree_reference(monkeypatch):
    """A batch with only inline file content has no reason to explore, so it must keep the
    adapter's default effort rather than unconditionally capping every findings call."""
    fake_adapter = _FakeStructuredOutputAdapter('{"findings": []}')
    monkeypatch.setattr(code_review_steps, "_resolve_headless_adapter", lambda _pref: fake_adapter)

    ctx = WorkflowContext()
    ctx.textual = _FakeTextual()
    ctx.data["review_context_batches"] = [_make_findings_batch("batch_1", {"a.py": 100})]
    ctx.data["review_budget"] = ReviewBudget(
        deep_max_prompt_chars=6000,
        triage_max_prompt_chars=6000,
        max_comment_entries=5,
        deep_timeout_base_seconds=300,
        deep_timeout_per_file_seconds=120,
        deep_timeout_max_seconds=1500,
    )
    ctx.data["cli_preference"] = "auto"
    ctx.data["project_root"] = "/tmp/project"

    result = ai_review_findings(ctx)

    assert isinstance(result, Success)
    assert fake_adapter.calls[0]["effort"] is None


def test_ai_thread_resolution_parses_markdown_fenced_response(monkeypatch):
    """review-batching-006: ai_thread_resolution used to hand-roll its own fence
    stripping and JSON-slice extraction. It must now share the same
    `extract_json_payload()` helper as ai_review_findings/ai_review_plan."""
    fake_adapter = _FakeFencedAdapter('```json\n[{"thread_id": "t1", "decision": "resolved"}]\n```')
    monkeypatch.setattr(code_review_steps, "_resolve_headless_adapter", lambda _pref: fake_adapter)

    ctx = WorkflowContext()
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

    ctx = WorkflowContext()
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


# ---------------------------------------------------------------------------
# File-read access guard: the fallback root is the user's own checkout, which is
# usually on a different branch than the PR head.
# ---------------------------------------------------------------------------

_HEAD_SHA = "a" * 40
_OTHER_SHA = "b" * 40


def _read_access_ctx(*, head_sha=_HEAD_SHA, checkout_sha=_HEAD_SHA, dirty=False, with_git=True):
    ctx = WorkflowContext()
    ctx.textual = _FakeTextual()
    ctx.data["review_commit_sha"] = head_sha
    if with_git:
        ctx.git = Mock()
        ctx.git.get_current_commit.return_value = ClientSuccess(data=checkout_sha, message="ok")
        ctx.git.has_uncommitted_changes.return_value = ClientSuccess(data=dirty, message="ok")
    else:
        ctx.git = None
    return ctx


def test_file_read_access_trusts_worktree_without_querying_git():
    ctx = _read_access_ctx(checkout_sha=_OTHER_SHA)

    access = code_review_steps._resolve_file_read_access(ctx, "/tmp/titan-review-1")

    assert access.allowed is True
    assert access.source == "worktree"
    ctx.git.get_current_commit.assert_not_called()


def test_file_read_access_allows_clean_checkout_at_pr_head():
    ctx = _read_access_ctx()

    access = code_review_steps._resolve_file_read_access(ctx, None)

    assert access.allowed is True
    assert access.source == "checkout"


def test_file_read_access_blocks_checkout_on_another_branch():
    """The failure mode: create_worktree failed (on_error: continue) and the user is
    sitting on an unrelated branch."""
    ctx = _read_access_ctx(checkout_sha=_OTHER_SHA)

    access = code_review_steps._resolve_file_read_access(ctx, None)

    assert access.allowed is False


def test_file_read_access_blocks_dirty_checkout():
    ctx = _read_access_ctx(dirty=True)

    access = code_review_steps._resolve_file_read_access(ctx, None)

    assert access.allowed is False


def test_file_read_access_blocks_when_git_queries_fail():
    ctx = _read_access_ctx()
    ctx.git.get_current_commit.return_value = ClientError(
        error_message="not a repo", error_code="GIT_ERROR"
    )

    access = code_review_steps._resolve_file_read_access(ctx, None)

    assert access.allowed is False


def test_file_read_access_blocks_without_git_client():
    ctx = _read_access_ctx(with_git=False)

    access = code_review_steps._resolve_file_read_access(ctx, None)

    assert access.allowed is False


def test_file_read_access_blocks_when_head_sha_unknown():
    ctx = _read_access_ctx(head_sha="")

    access = code_review_steps._resolve_file_read_access(ctx, None)

    assert access.allowed is False


# ---------------------------------------------------------------------------
# Submit-time head SHA re-check: the bundle SHA is minutes old by then
# ---------------------------------------------------------------------------


def _drift_ctx(current_sha_result):
    ctx = WorkflowContext()
    ctx.textual = _FakeTextual()
    ctx.github = Mock()
    ctx.github.get_pr_commit_sha.return_value = current_sha_result
    return ctx


def test_submit_sha_drift_detected_when_pr_was_pushed_to():
    ctx = _drift_ctx(ClientSuccess(data="b" * 40, message="ok"))

    drift = code_review_steps._detect_submit_time_sha_drift(ctx, 123, "a" * 40)

    assert drift.drifted is True
    assert drift.current_sha == "b" * 40


def test_submit_sha_no_drift_when_head_is_unchanged():
    ctx = _drift_ctx(ClientSuccess(data="a" * 40, message="ok"))

    drift = code_review_steps._detect_submit_time_sha_drift(ctx, 123, "a" * 40)

    assert drift.drifted is False


def test_submit_sha_recheck_failure_does_not_block_the_submission():
    """The publish gate already validates lines against the diff, so a failed
    re-check must not degrade or cancel an otherwise valid review."""
    ctx = _drift_ctx(ClientError(error_message="api down", error_code="GH_ERROR"))

    drift = code_review_steps._detect_submit_time_sha_drift(ctx, 123, "a" * 40)

    assert drift.drifted is False


def test_resolve_drift_changed_files_returns_pushed_paths():
    """On drift, the push's touched files come from a local diff so only their
    comments degrade — after a fetch, since the new head postdates the review's own."""
    from titan_plugin_github.operations.review_action_operations import detect_head_sha_drift

    ctx = WorkflowContext()
    ctx.git = Mock()
    ctx.git.fetch.return_value = ClientSuccess(data=None, message="ok")
    ctx.git.get_changed_files.return_value = ClientSuccess(
        data=["src/touched.py"], message="ok"
    )
    drift = detect_head_sha_drift("a" * 40, "b" * 40)

    paths = code_review_steps._resolve_drift_changed_files(ctx, drift)

    assert paths == {"src/touched.py"}
    ctx.git.fetch.assert_called_once()
    ctx.git.get_changed_files.assert_called_once_with("a" * 40, "b" * 40)


def test_resolve_drift_changed_files_unknowable_returns_none():
    """git unavailable or failing → None, so the caller degrades everything
    (never publishes stale anchors on a hunch)."""
    from titan_plugin_github.operations.review_action_operations import detect_head_sha_drift

    drift = detect_head_sha_drift("a" * 40, "b" * 40)

    no_git_ctx = WorkflowContext()
    no_git_ctx.git = None
    assert code_review_steps._resolve_drift_changed_files(no_git_ctx, drift) is None

    failing_ctx = WorkflowContext()
    failing_ctx.git = Mock()
    failing_ctx.git.fetch.return_value = ClientSuccess(data=None, message="ok")
    failing_ctx.git.get_changed_files.return_value = ClientError(
        error_message="bad object", error_code="DIFF_ERROR"
    )
    assert code_review_steps._resolve_drift_changed_files(failing_ctx, drift) is None


def test_submit_sha_drift_ignores_surrounding_whitespace():
    ctx = _drift_ctx(ClientSuccess(data=f"  {'a' * 40}\n", message="ok"))

    drift = code_review_steps._detect_submit_time_sha_drift(ctx, 123, "a" * 40)

    assert drift.drifted is False


# ============================================================================
# ai_review_findings concurrency (review-quality-006)
# ============================================================================


class _FakeConcurrencyTrackingAdapter:
    """Fake adapter that records how many executes overlap in flight."""

    cli_name = SupportedCLI.CLAUDE
    supports_structured_output = False
    supports_tool_restriction = False
    supports_effort_control = False

    def __init__(self, stdout: str = "[]", block_until: int | None = None):
        self._stdout = stdout
        self._lock = threading.Lock()
        self._in_flight = 0
        self.max_in_flight = 0
        self.calls = 0
        # When set, every call waits until `block_until` calls are in flight —
        # proves genuine overlap (deadlocks under a sequential executor).
        self._barrier = threading.Barrier(block_until, timeout=10) if block_until else None

    def is_available(self) -> bool:
        return True

    def execute(self, prompt: str, cwd=None, timeout=None, json_schema=None, disallowed_tools=None, effort=None) -> HeadlessResponse:
        with self._lock:
            self.calls += 1
            self._in_flight += 1
            self.max_in_flight = max(self.max_in_flight, self._in_flight)
        try:
            if self._barrier:
                self._barrier.wait()
            return HeadlessResponse(stdout=self._stdout, stderr="", exit_code=0)
        finally:
            with self._lock:
                self._in_flight -= 1


def _concurrency_ctx(monkeypatch, batch_count: int, concurrency: int) -> WorkflowContext:
    from titan_plugin_github.models.review_profile_models import ReviewProfile

    ctx = WorkflowContext()
    ctx.textual = _FakeTextual()
    monkeypatch.setattr(code_review_steps, "FINDINGS_BATCH_CONCURRENCY", concurrency)
    ctx.data["review_profile"] = ReviewProfile()
    ctx.data["review_context_batches"] = [
        _make_findings_batch(f"batch_{i}", {f"f{i}.py": 100}) for i in range(batch_count)
    ]
    ctx.data["review_budget"] = ReviewBudget(
        deep_max_prompt_chars=20000,
        triage_max_prompt_chars=20000,
        max_comment_entries=5,
        deep_timeout_base_seconds=300,
        deep_timeout_per_file_seconds=120,
        deep_timeout_max_seconds=1500,
    )
    ctx.data["cli_preference"] = "auto"
    ctx.data["project_root"] = "/tmp/project"
    return ctx


def test_ai_review_findings_runs_batches_concurrently(monkeypatch):
    """review-quality-006: with FINDINGS_BATCH_CONCURRENCY=2, two batches must be
    in flight at the same time (the barrier only releases when both arrive — this
    test deadlocks/times out under a sequential executor)."""
    fake_adapter = _FakeConcurrencyTrackingAdapter(stdout='[{"title": "Bug"}]', block_until=2)
    monkeypatch.setattr(code_review_steps, "_resolve_headless_adapter", lambda _pref: fake_adapter)

    ctx = _concurrency_ctx(monkeypatch, batch_count=2, concurrency=2)
    result = ai_review_findings(ctx)

    assert isinstance(result, Success)
    assert fake_adapter.max_in_flight == 2
    assert ctx.data["raw_findings"] == [{"title": "Bug"}, {"title": "Bug"}]
    assert ctx.data["ai_findings_failed"] is False


def test_ai_review_findings_concurrency_one_stays_sequential(monkeypatch):
    fake_adapter = _FakeConcurrencyTrackingAdapter(stdout="[]")
    monkeypatch.setattr(code_review_steps, "_resolve_headless_adapter", lambda _pref: fake_adapter)

    ctx = _concurrency_ctx(monkeypatch, batch_count=3, concurrency=1)
    result = ai_review_findings(ctx)

    assert isinstance(result, Success)
    assert fake_adapter.calls == 3
    assert fake_adapter.max_in_flight == 1


def test_ai_review_findings_pool_never_exceeds_configured_concurrency(monkeypatch):
    fake_adapter = _FakeConcurrencyTrackingAdapter(stdout="[]")
    monkeypatch.setattr(code_review_steps, "_resolve_headless_adapter", lambda _pref: fake_adapter)

    ctx = _concurrency_ctx(monkeypatch, batch_count=6, concurrency=2)
    result = ai_review_findings(ctx)

    assert isinstance(result, Success)
    assert fake_adapter.calls == 6
    assert fake_adapter.max_in_flight <= 2


def test_ai_review_findings_worker_crash_marks_batch_failed_not_step_crash(monkeypatch):
    """An adapter exception inside a worker must degrade to a failed batch (visible),
    not crash the whole step."""

    class _ExplodingAdapter:
        cli_name = SupportedCLI.CLAUDE
        supports_structured_output = False
        supports_tool_restriction = False
        supports_effort_control = False

        def is_available(self) -> bool:
            return True

        def execute(self, *args, **kwargs):
            raise RuntimeError("boom")

    monkeypatch.setattr(code_review_steps, "_resolve_headless_adapter", lambda _pref: _ExplodingAdapter())

    ctx = _concurrency_ctx(monkeypatch, batch_count=1, concurrency=2)
    result = ai_review_findings(ctx)

    # Single batch crashed → 0/1 produced output → visible Error (review-quality-005).
    assert isinstance(result, Error)
    assert ctx.data["raw_findings"] == []
    assert ctx.data["ai_findings_failed"] is True


# ============================================================================
# ai_review_findings empty-findings rescue (review-quality-007)
# ============================================================================


def _rescue_ctx(adapter_stdouts: list[str]) -> tuple[WorkflowContext, "_FakeSequentialAdapter"]:
    fake_adapter = _FakeSequentialAdapter(adapter_stdouts)
    ctx = WorkflowContext()
    ctx.textual = _FakeTextual()
    ctx.data["review_profile"] = ReviewProfile()
    ctx.data["review_context_batches"] = [_make_findings_batch("batch_1", {"a.py": 100})]
    ctx.data["review_budget"] = ReviewBudget(
        deep_max_prompt_chars=20000,
        triage_max_prompt_chars=20000,
        max_comment_entries=5,
        deep_timeout_base_seconds=300,
        deep_timeout_per_file_seconds=120,
        deep_timeout_max_seconds=1500,
    )
    ctx.data["review_diff"] = (
        "diff --git a/border.py b/border.py\n"
        "index 111..222 100644\n"
        "--- a/border.py\n"
        "+++ b/border.py\n"
        "@@ -1,2 +1,3 @@\n"
        " context\n"
        "+added line\n"
        " context\n"
    )
    ctx.data["cli_preference"] = "auto"
    ctx.data["project_root"] = "/tmp/project"
    return ctx, fake_adapter


def test_ai_review_findings_reports_nothing_when_there_is_nothing(monkeypatch):
    """A review with nothing to say says nothing, and makes no further calls.

    This replaces two tests for the empty-findings rescue, which reviewed extra
    "borderline" files whenever the batches came back empty. That was pressure to produce
    a finding, and the condition it compensated for is gone: it existed because only 12
    files of any PR were ever looked at, so an empty result really could mean the wrong 12
    had been chosen.
    """
    ctx, fake_adapter = _rescue_ctx(["[]"])
    monkeypatch.setattr(code_review_steps, "_resolve_headless_adapter", lambda _pref: fake_adapter)

    result = ai_review_findings(ctx)

    assert isinstance(result, Success)
    assert len(fake_adapter.calls) == 1  # the batch, and no rescue after it
    assert ctx.data["raw_findings"] == []
    assert ctx.data["ai_findings_failed"] is False


# ============================================================================
# Timeout fallback for worktree_reference batches (+ early worktree release)
# ============================================================================


class _FakeExitCodeAdapter:
    """Fake adapter scripted with (exit_code, stdout) tuples, one per call."""

    cli_name = SupportedCLI.CLAUDE
    supports_structured_output = False
    supports_tool_restriction = False
    supports_effort_control = False

    def __init__(self, script: list[tuple[int, str]]):
        self._script = list(script)
        self.calls: list[dict] = []

    def is_available(self) -> bool:
        return True

    def execute(self, prompt: str, cwd=None, timeout=None, json_schema=None, disallowed_tools=None, effort=None) -> HeadlessResponse:
        self.calls.append(
            {
                "prompt": prompt,
                "effort": effort,
                "timeout": timeout,
                "disallowed_tools": disallowed_tools,
                "json_schema": json_schema,
            }
        )
        exit_code, stdout = self._script[len(self.calls) - 1]
        return HeadlessResponse(stdout=stdout, stderr="", exit_code=exit_code)


def _timeout_ctx(adapter_script: list[tuple[int, str]], *, worktree_reference: bool = True):
    fake_adapter = _FakeExitCodeAdapter(adapter_script)
    ctx = WorkflowContext()
    ctx.textual = _FakeTextual()
    ctx.data["review_profile"] = ReviewProfile()
    if worktree_reference:
        ctx.data["review_context_batches"] = [
            _make_worktree_reference_batch("batch_1", "border.py")
        ]
    else:
        ctx.data["review_context_batches"] = [_make_findings_batch("batch_1", {"border.py": 100})]
    ctx.data["review_budget"] = ReviewBudget(
        deep_max_prompt_chars=20000,
        triage_max_prompt_chars=20000,
        max_comment_entries=5,
        deep_timeout_base_seconds=300,
        deep_timeout_per_file_seconds=120,
        deep_timeout_max_seconds=1500,
    )
    ctx.data["review_diff"] = (
        "diff --git a/border.py b/border.py\n"
        "index 111..222 100644\n"
        "--- a/border.py\n"
        "+++ b/border.py\n"
        "@@ -1,2 +1,3 @@\n"
        " context\n"
        "+added line\n"
        " context\n"
    )
    ctx.data["cli_preference"] = "auto"
    ctx.data["project_root"] = "/tmp/project"
    return ctx, fake_adapter


def test_ai_review_findings_retries_timed_out_worktree_batch_with_hunks(monkeypatch):
    """A timed-out worktree_reference batch reviewed NOTHING — one bounded retry with
    inline hunks turns a total loss into guaranteed coverage of the batch's files."""
    ctx, fake_adapter = _timeout_ctx(
        [
            (124, ""),  # batch_1: CLI timeout while exploring the worktree
            (0, '[{"title": "Found on retry", "path": "border.py"}]'),  # batch_1_retry
        ]
    )
    monkeypatch.setattr(code_review_steps, "_resolve_headless_adapter", lambda _pref: fake_adapter)

    result = ai_review_findings(ctx)

    assert isinstance(result, Success)
    assert len(fake_adapter.calls) == 2
    retry_prompt = fake_adapter.calls[1]["prompt"]
    assert "added line" in retry_prompt  # inline hunks, no worktree exploration
    assert "Read from worktree" not in retry_prompt
    assert ctx.data["raw_findings"] == [{"title": "Found on retry", "path": "border.py"}]
    assert ctx.data["ai_findings_failed"] is False


def test_ai_review_findings_no_timeout_retry_for_inline_batches(monkeypatch):
    """Timeouts on batches that already had inline hunks don't retry — the fallback
    only exists for worktree_reference exploration blowups."""
    ctx, fake_adapter = _timeout_ctx([(124, "")], worktree_reference=False)
    monkeypatch.setattr(code_review_steps, "_resolve_headless_adapter", lambda _pref: fake_adapter)

    result = ai_review_findings(ctx)

    assert isinstance(result, Error)  # 0/1 batches produced output (005)
    assert len(fake_adapter.calls) == 1


def test_ai_review_findings_timeout_retry_failure_keeps_batch_failed(monkeypatch):
    ctx, fake_adapter = _timeout_ctx(
        [
            (124, ""),  # batch_1 timeout
            (1, ""),  # retry also fails
        ]
    )
    monkeypatch.setattr(code_review_steps, "_resolve_headless_adapter", lambda _pref: fake_adapter)

    result = ai_review_findings(ctx)

    assert isinstance(result, Error)  # still 0/N succeeded
    assert len(fake_adapter.calls) == 2


def _multi_hunk_diff(path: str, *, hunks: int, hunk_chars: int) -> str:
    """A diff for `path` with `hunks` separate hunks, each roughly `hunk_chars` long."""
    header = (
        f"diff --git a/{path} b/{path}\n"
        f"index 111..222 100644\n"
        f"--- a/{path}\n"
        f"+++ b/{path}\n"
    )
    body = ""
    for index in range(hunks):
        start = 1 + index * 40
        body += f"@@ -{start},2 +{start},3 @@\n context\n+{'x' * hunk_chars}\n context\n"
    return header + body


def test_ai_review_findings_splits_an_oversized_timeout_fallback_instead_of_dropping_it(
    monkeypatch,
):
    """A fallback that does not fit the budget is SPLIT, not abandoned.

    This is the defect measured on PR #254: the fallback prompt for one file came to
    149,353 chars against an 18,000 budget, the retry returned early keeping the original
    timeout, and the file went unreviewed in three consecutive runs with no UI line and no
    log event saying so.
    """
    ctx, fake_adapter = _timeout_ctx(
        [
            (124, ""),  # batch_1 times out exploring the worktree
            (0, '[{"title": "First half", "path": "border.py"}]'),
            (0, '[{"title": "Second half", "path": "border.py"}]'),
        ]
    )
    # Two ~1200-char hunks build a 5,207-char fallback prompt; each half builds 3,998. The
    # budget sits between them, so splitting is the only way through. These figures move
    # whenever the instruction block changes — if this fails after a prompt edit, re-measure
    # rather than widening the budget until it passes.
    ctx.data["review_diff"] = _multi_hunk_diff("border.py", hunks=2, hunk_chars=1200)
    ctx.data["review_budget"] = ctx.data["review_budget"].model_copy(
        update={"deep_max_prompt_chars": 4500}
    )
    monkeypatch.setattr(code_review_steps, "_resolve_headless_adapter", lambda _pref: fake_adapter)

    result = ai_review_findings(ctx)

    assert isinstance(result, Success)
    assert len(fake_adapter.calls) == 3  # timeout + two split retries, not one drop
    assert ctx.data["raw_findings"] == [
        {"title": "First half", "path": "border.py"},
        {"title": "Second half", "path": "border.py"},
    ]
    assert ctx.data["ai_findings_failed"] is False


def test_ai_review_findings_says_so_when_a_timed_out_batch_cannot_be_retried(monkeypatch):
    """No hunks means nothing bounded to retry with — the file is unreviewed, and that
    is stated rather than left to look like any other failure."""
    ctx, fake_adapter = _timeout_ctx([(124, "")])
    ctx.data["review_diff"] = ""  # no hunks for border.py
    monkeypatch.setattr(code_review_steps, "_resolve_headless_adapter", lambda _pref: fake_adapter)

    result = ai_review_findings(ctx)

    assert isinstance(result, Error)  # 0/1 batches produced output
    assert len(fake_adapter.calls) == 1
    warnings = " ".join(ctx.textual.warnings)
    assert "border.py" in warnings
    assert "NOT reviewed" in warnings


def test_ai_review_findings_derives_the_call_timeout_from_the_batch_size(monkeypatch):
    """The flat 300 s was chosen when a batch held one file; a packed batch measured
    251 s at medium effort for ten files, so the deadline has to scale with them."""
    ctx, fake_adapter = _timeout_ctx([(0, "[]")], worktree_reference=False)
    ctx.data["review_context_batches"] = [
        _make_findings_batch("batch_1", {"a.py": 100, "b.py": 100, "c.py": 100})
    ]
    monkeypatch.setattr(code_review_steps, "_resolve_headless_adapter", lambda _pref: fake_adapter)

    result = ai_review_findings(ctx)

    assert isinstance(result, Success)
    budget = ctx.data["review_budget"]
    assert fake_adapter.calls[0]["timeout"] == (
        budget.deep_timeout_base_seconds + 2 * budget.deep_timeout_per_file_seconds
    )


def test_release_review_worktree_cleans_and_clears_context(monkeypatch):
    import titan_plugin_github.operations as gh_operations

    removed = []
    monkeypatch.setattr(
        gh_operations, "cleanup_worktree", lambda git, path: removed.append(path) or True
    )

    ctx = WorkflowContext()
    ctx.textual = _FakeTextual()
    ctx.git = Mock()
    ctx.data["worktree_created"] = True
    ctx.data["worktree_path"] = "/tmp/wt/titan-review-9"

    code_review_steps._release_review_worktree(ctx)

    assert removed == ["/tmp/wt/titan-review-9"]
    assert ctx.data["worktree_created"] is False
    assert ctx.data["worktree_path"] is None


def test_validate_review_actions_releases_worktree_even_with_no_actions(monkeypatch):
    """The early-release must also cover the no-actions path: the user can still quit
    at the submit prompt afterwards, and the worktree must not depend on reaching the
    final cleanup step."""
    import titan_plugin_github.operations as gh_operations

    removed = []
    monkeypatch.setattr(
        gh_operations, "cleanup_worktree", lambda git, path: removed.append(path) or True
    )

    ctx = WorkflowContext()
    ctx.textual = _FakeTextual()
    ctx.git = Mock()
    ctx.data["review_action_proposals"] = []
    ctx.data["worktree_created"] = True
    ctx.data["worktree_path"] = "/tmp/wt/titan-review-9"

    result = code_review_steps.validate_review_actions(ctx)

    assert isinstance(result, Skip)
    assert removed == ["/tmp/wt/titan-review-9"]


# ============================================================================
# findings-phase cost is reported even when the phase is abandoned (cov-001/005)
# ============================================================================


def test_findings_phase_reports_its_cost_even_when_interrupted(monkeypatch):
    """The phase a user interrupts is the one whose cost they most want to know.

    A real run on 2026-09-22 was stopped mid-findings and emitted no cost summary at
    all, because it was only logged on the success path. WorkflowAborted is a
    BaseException, so `finally` is the only construct that still runs.
    """
    import pytest

    from titan_cli.core.interrupt import WorkflowAborted

    scopes = []

    class _Ctx:
        data = {}

    monkeypatch.setattr(
        code_review_steps, "_ai_review_findings", lambda _ctx: (_ for _ in ()).throw(WorkflowAborted())
    )
    monkeypatch.setattr(
        code_review_steps, "log_review_ai_cost", lambda _ctx, scope: scopes.append(scope)
    )

    with pytest.raises(BaseException):
        code_review_steps.ai_review_findings(_Ctx())

    assert scopes == ["findings_phase"]


def test_findings_phase_reports_its_cost_on_the_success_path_too(monkeypatch):
    scopes = []

    class _Ctx:
        data = {}

    monkeypatch.setattr(code_review_steps, "_ai_review_findings", lambda _ctx: Success("done"))
    monkeypatch.setattr(
        code_review_steps, "log_review_ai_cost", lambda _ctx, scope: scopes.append(scope)
    )

    assert isinstance(code_review_steps.ai_review_findings(_Ctx()), Success)
    assert scopes == ["findings_phase"]


def test_a_failure_reason_carries_the_cli_s_own_words():
    """A pattern list only recognises the failures it has already seen, and the one it
    misses is the one worth reading.

    Measured 2026-09-22: claude exited 1 with "You've hit your session limit · resets
    6:30pm" in stderr, and the reviewer was told "'claude' exited with code 1" while the
    whole review was discarded."""
    from titan_cli.external_cli.adapters.base import HeadlessResponse

    session_limit = HeadlessResponse(
        stdout="", stderr="You've hit your session limit · resets 6:30pm (Europe/Madrid)", exit_code=1
    )
    reason = code_review_steps._cli_failure_reason(session_limit, "claude")

    assert "usage quota" in reason  # recognised as quota, so the advice is right
    assert "resets 6:30pm" in reason  # and the CLI's own words survive


def test_a_failure_reason_stays_clean_when_the_cli_only_produced_noise():
    """Pasting a stack trace into a one-line status is worse than saying nothing."""
    from titan_cli.external_cli.adapters.base import HeadlessResponse

    noisy = HeadlessResponse(stdout="", stderr="x" * 5000, exit_code=1)

    assert code_review_steps._cli_failure_reason(noisy, "claude") == "'claude' exited with code 1"




def test_a_question_with_a_finding_is_confirmed_and_never_also_dismissed():
    """Run 0b420ac0 reported "1 confirmed · 4 dismissed" for 4 questions: the session
    reported a finding on a flagged file AND dismissed its question, and both were
    counted. The finding is what reaches the PR, so it is the outcome."""
    from types import SimpleNamespace

    class _Recording(_FakeTextual):
        def __init__(self):
            super().__init__()
            self.dims: list[str] = []

        def dim_text(self, text):
            self.dims.append(text)

    ctx = Mock()
    ctx.textual = _Recording()
    batch = SimpleNamespace(triage_suspicions=[{"path": "a.kt"}, {"path": "b.kt"}])
    dismissed = [{"path": "a.kt", "reason": "checked"}, {"path": "b.kt", "reason": "fine"}]
    findings = [{"path": "a.kt", "line": 3}]

    code_review_steps._render_settled_questions(ctx, [batch], dismissed, findings)

    assert "First-pass questions: 1 confirmed · 1 dismissed" in ctx.textual.dims
    assert not any(line.startswith("  dismissed a.kt") for line in ctx.textual.dims)
    assert not ctx.textual.warnings  # nothing left unanswered


def test_the_settle_rule_asks_for_defects_seen_while_settling():
    """The old rule, "do not review the rest of a flagged file", made a session discard
    a real defect it had already found (run 0b420ac0: "I didn't review this further
    because it's outside the question")."""
    import inspect

    from titan_plugin_github.operations import findings_operations

    source = inspect.getsource(findings_operations)
    assert "Do not review the rest of a flagged file" not in source
    assert "a defect you SEE while settling it is a finding like any other" in source


def test_a_call_record_keeps_the_cached_input_the_cli_reported():
    """Anthropic counts cached input outside input_tokens, so a 90k-char prompt logged
    as input_tokens=107 with the cache figures dropped — which read as a broken counter
    on the newer models, when the record simply never kept those two fields."""
    from titan_cli.external_cli.adapters.base import CliUsage

    usage = CliUsage(input_tokens=107, output_tokens=6779, cache_read_tokens=5000,
                     cache_write_tokens=30000, reasoning_tokens=900, cost_usd=0.58)
    adapter = Mock()
    adapter.cli_name = SupportedCLI.CLAUDE
    adapter.execute.return_value = HeadlessResponse(stdout="ok", stderr="", exit_code=0, usage=usage)
    ctx = Mock()
    ctx.data = {}

    code_review_steps._PinnedModelCli(adapter, "sonnet", ctx=ctx, phase="code_review_findings").execute("p")

    record = ctx.data[code_review_steps.REVIEW_AI_CALLS_KEY][0]
    assert (record.cache_read_tokens, record.cache_write_tokens, record.reasoning_tokens) == (5000, 30000, 900)


def test_the_review_plan_reads_every_deep_file_and_names_the_rest():
    """One step decides the tiers and the deep session's files: no scorer, no model."""
    from titan_plugin_github.steps.code_review_steps import build_review_plan

    ctx = WorkflowContext()
    ctx.textual = _FakeTextual()
    ctx.data["review_profile"] = ReviewProfile(
        file_roles={"business_logic": ["**/services/**"]},
        attention={"business_logic": "deep", "docs_or_generated": "skip"},
    )
    ctx.data["review_checklist"] = []
    ctx.data["change_manifest"] = ChangeManifest(
        pr=PullRequestManifest(number=1, title="t", base="main", head="f", author="a", description=""),
        files=[
            MockChangedFile(path="app/services/pay.py", status="modified", additions=5, deletions=1),
            MockChangedFile(path="app/misc/util.py", status="modified", additions=5, deletions=1),
            MockChangedFile(path="README.md", status="modified", additions=1, deletions=0, is_docs=True),
        ],
        total_additions=11,
        total_deletions=2,
    )

    result = build_review_plan(ctx)

    assert isinstance(result, Success)
    plan = result.metadata["validated_review_plan"]
    assert [f.path for f in plan.focus_files] == ["app/services/pay.py"]
    assert result.metadata["attention_plan"].counts == {"deep": 1, "glance": 1, "skip": 1}
    assert "review_budget" in result.metadata


def test_the_review_plan_exits_when_nothing_is_reviewable():
    from titan_plugin_github.review_profiles import DEFAULT_REVIEW_PROFILE
    from titan_plugin_github.steps.code_review_steps import build_review_plan

    ctx = WorkflowContext()
    ctx.textual = _FakeTextual()
    ctx.data["review_profile"] = DEFAULT_REVIEW_PROFILE
    ctx.data["review_checklist"] = []
    ctx.data["change_manifest"] = ChangeManifest(
        pr=PullRequestManifest(number=1, title="t", base="main", head="f", author="a", description=""),
        files=[MockChangedFile(path="docs/readme.md", status="modified", additions=1, deletions=0, is_docs=True)],
        total_additions=1,
        total_deletions=0,
    )

    assert isinstance(build_review_plan(ctx), Exit)


def test_the_review_config_renders_with_a_profile_written_for_the_old_pipeline(tmp_path):
    """The render read `profile.candidate_scoring` after the field was deleted, and the
    Review PR workflow died at Build Review Checklist on ragnarok. It must render with
    a real resolution, and name the keys it ignored."""
    from titan_plugin_github.managers.checklist_manager import ChecklistManager
    from titan_plugin_github.managers.review_profile_manager import ReviewProfileManager

    review_dir = tmp_path / ".titan" / "review"
    review_dir.mkdir(parents=True)
    (review_dir / "profile.yaml").write_text("candidate_scoring: []\n", encoding="utf-8")

    class _Recording(_FakeTextual):
        def dim_text(self, _text):
            pass

    ctx = WorkflowContext()
    ctx.textual = _Recording()
    code_review_steps._render_review_config(
        ctx,
        ReviewProfileManager(project_root=tmp_path).resolve(),
        ChecklistManager(project_root=tmp_path).resolve(),
    )

    assert any("candidate_scoring" in warning for warning in ctx.textual.warnings)
