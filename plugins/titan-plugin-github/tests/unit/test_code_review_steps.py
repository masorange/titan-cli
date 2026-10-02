from unittest.mock import Mock

from titan_cli.core.result import ClientError, ClientSuccess
from titan_cli.engine import WorkflowContext
from titan_cli.engine.results import Error, Exit, Skip, Success
from titan_cli.external_cli.adapters import HeadlessResponse
from titan_cli.external_cli.adapters.base import SupportedCLI
from titan_plugin_github.models.review_models import (
    ChangeManifest,
    PullRequestManifest,
    ReferencedCommitContext,
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

    def collapsible_list(self, _entries, classes=""):
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

class _FakeReviewAdapter:
    """Fake headless adapter scripted with (exit_code, stdout) per call, recording each call."""

    cli_name = SupportedCLI.CLAUDE

    def __init__(self, script, *, structured=False, restricts=False, effort=False, subagents=False):
        self._script = list(script)
        self.calls: list[dict] = []
        self.supports_structured_output = structured
        self.supports_tool_restriction = restricts
        self.supports_effort_control = effort
        self.supports_subagents = subagents

    def is_available(self) -> bool:
        return True

    def execute(self, prompt, **kwargs) -> HeadlessResponse:
        self.calls.append({"prompt": prompt, **kwargs})
        exit_code, stdout = self._script[len(self.calls) - 1]
        return HeadlessResponse(stdout=stdout, stderr="", exit_code=exit_code)


def _review_ctx(tmp_path, monkeypatch, adapter) -> WorkflowContext:
    from titan_plugin_github.models.review_models import ChangedFileEntry

    (tmp_path / "a.py").write_text("x = 1\n")
    (tmp_path / "router.py").write_text("y = 2\n")
    monkeypatch.setattr(code_review_steps, "_resolve_headless_adapter", lambda _pref: adapter)
    ctx = WorkflowContext()
    ctx.textual = _FakeTextual()
    ctx.textual.loading = lambda _text: __import__("contextlib").nullcontext()
    ctx.data["worktree_path"] = str(tmp_path)
    ctx.data["change_manifest"] = ChangeManifest(
        pr=PullRequestManifest(number=9, title="T", base="main", head="f", author="a", description="D"),
        files=[ChangedFileEntry(path="a.py", status=FileChangeStatus.MODIFIED)],
        total_additions=1,
        total_deletions=0,
    )
    return ctx


_ONE_FINDING = (
    '{"findings": [{"path": "a.py", "line": 1, "severity": "important", '
    '"title": "Bug", "body": "Explain", "snippet": "x = 1"}]}'
)


def test_the_review_runs_one_session_in_the_worktree_and_maps_its_findings(tmp_path, monkeypatch):
    adapter = _FakeReviewAdapter([(0, _ONE_FINDING)])
    ctx = _review_ctx(tmp_path, monkeypatch, adapter)

    result = ai_review_findings(ctx)

    assert isinstance(result, Success)
    assert len(adapter.calls) == 1
    call = adapter.calls[0]
    assert call["cwd"] == str(tmp_path)
    assert "Review pull request #9" in call["prompt"]
    assert ctx.data["ai_findings_failed"] is False
    [finding] = ctx.data["raw_findings"]
    assert finding["why"] == finding["suggested_comment"] == "Explain"
    assert finding["evidence"] == "x = 1"


def test_the_session_gets_subagents_read_only_git_effort_and_a_ceiling_where_enforceable(tmp_path, monkeypatch):
    from titan_plugin_github.operations.findings_operations import (
        REVIEW_ALLOWED_TOOLS,
        REVIEW_DISALLOWED_TOOLS,
        REVIEW_EFFORT,
        REVIEW_MAX_BUDGET_USD,
        REVIEW_TIMEOUT_SECONDS,
        free_review_json_schema,
    )

    adapter = _FakeReviewAdapter([(0, _ONE_FINDING)], structured=True, restricts=True, effort=True)
    ctx = _review_ctx(tmp_path, monkeypatch, adapter)

    ai_review_findings(ctx)

    call = adapter.calls[0]
    assert call["json_schema"] == free_review_json_schema()
    assert call["disallowed_tools"] == list(REVIEW_DISALLOWED_TOOLS)
    assert "Agent" not in call["disallowed_tools"]
    assert call["allowed_tools"] == list(REVIEW_ALLOWED_TOOLS)
    assert call["effort"] == REVIEW_EFFORT
    assert call["max_budget_usd"] == REVIEW_MAX_BUDGET_USD
    assert call["timeout"] == REVIEW_TIMEOUT_SECONDS


def test_a_cli_that_cannot_restrict_tools_gets_no_tool_options(tmp_path, monkeypatch):
    adapter = _FakeReviewAdapter([(0, _ONE_FINDING)])
    ctx = _review_ctx(tmp_path, monkeypatch, adapter)

    ai_review_findings(ctx)

    call = adapter.calls[0]
    assert call["json_schema"] is None
    assert call["disallowed_tools"] is None
    assert call["allowed_tools"] is None
    assert call["effort"] is None


def test_findings_about_real_files_outside_the_pr_are_kept_and_invented_ones_dropped(tmp_path, monkeypatch):
    stdout = (
        '{"findings": ['
        '{"path": "router.py", "severity": "blocking", "title": "Regression", "body": "b"},'
        '{"path": "ghost.py", "severity": "nit", "title": "Made up", "body": "b"}]}'
    )
    adapter = _FakeReviewAdapter([(0, stdout)])
    ctx = _review_ctx(tmp_path, monkeypatch, adapter)

    ai_review_findings(ctx)

    assert [f["path"] for f in ctx.data["raw_findings"]] == ["router.py"]
    assert any("1 finding(s)" in warning for warning in ctx.textual.warnings)


def test_a_prose_answer_is_reformatted_once(tmp_path, monkeypatch):
    adapter = _FakeReviewAdapter([(0, "I found a bug in a.py."), (0, '[{"path": "a.py", "severity": "nit", "title": "t", "body": "b"}]')])
    ctx = _review_ctx(tmp_path, monkeypatch, adapter)

    result = ai_review_findings(ctx)

    assert isinstance(result, Success)
    assert len(adapter.calls) == 2
    assert "I found a bug in a.py." in adapter.calls[1]["prompt"]
    assert len(ctx.data["raw_findings"]) == 1


def test_an_unreadable_answer_after_the_retry_fails_visibly(tmp_path, monkeypatch):
    adapter = _FakeReviewAdapter([(0, "prose"), (0, "still prose")])
    ctx = _review_ctx(tmp_path, monkeypatch, adapter)

    result = ai_review_findings(ctx)

    assert isinstance(result, Error)
    assert ctx.data["raw_findings"] == []
    assert ctx.data["ai_findings_failed"] is True


def test_a_failed_or_timed_out_session_fails_visibly_without_retrying(tmp_path, monkeypatch):
    adapter = _FakeReviewAdapter([(124, "")])
    ctx = _review_ctx(tmp_path, monkeypatch, adapter)

    result = ai_review_findings(ctx)

    assert isinstance(result, Error)
    assert len(adapter.calls) == 1
    assert ctx.data["ai_findings_failed"] is True


def test_a_review_with_nothing_to_say_says_nothing(tmp_path, monkeypatch):
    adapter = _FakeReviewAdapter([(0, '{"findings": []}')])
    ctx = _review_ctx(tmp_path, monkeypatch, adapter)

    result = ai_review_findings(ctx)

    assert isinstance(result, Success)
    assert ctx.data["raw_findings"] == []
    assert ctx.data["ai_findings_failed"] is False


def test_the_review_needs_a_worktree(tmp_path, monkeypatch):
    adapter = _FakeReviewAdapter([])
    ctx = _review_ctx(tmp_path, monkeypatch, adapter)
    ctx.data["worktree_path"] = None

    assert isinstance(ai_review_findings(ctx), Error)
    assert adapter.calls == []


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


def test_inline_code_is_highlighted_without_breaking_markup():
    """A model's `identifier` becomes bold; brackets in it must stay literal text."""
    from rich.text import Text

    from titan_cli.ui.tui.widgets.collapsible_list import escape_markup

    rendered = code_review_steps._highlight_inline_code(
        escape_markup("split `RGKWRONGOLDSPASSWORD` into `codes[0]` - intended?")
    )

    assert "[bold]RGKWRONGOLDSPASSWORD[/bold]" in rendered
    assert Text.from_markup(rendered).plain == "split RGKWRONGOLDSPASSWORD into codes[0] - intended?"


def test_the_repo_file_check_accepts_real_files_and_refuses_escapes(tmp_path):
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "Router.kt").write_text("x", encoding="utf-8")
    (tmp_path.parent / "outside.kt").write_text("x", encoding="utf-8")

    is_repo_file = code_review_steps._repo_file_checker(str(tmp_path))

    assert is_repo_file("app/Router.kt")
    assert not is_repo_file("app/Missing.kt")
    assert not is_repo_file("app")
    assert not is_repo_file("../outside.kt")
    assert not is_repo_file(str(tmp_path / "app" / "Router.kt"))
    assert code_review_steps._repo_file_checker(None) is None


def test_review_material_is_written_into_the_worktree(tmp_path):
    """Diffs, base versions and pr.md land under .titan-review/; a file the PR adds has no
    base version, and a failure to resolve the base writes nothing (None)."""
    from types import SimpleNamespace

    from titan_cli.core.result import ClientError, ClientSuccess

    from titan_plugin_github.managers.diff_context_manager import DiffContextManager
    from titan_plugin_github.models.review_enums import FileChangeStatus
    from titan_plugin_github.models.review_models import ChangeManifest, ChangedFileEntry, PullRequestManifest

    diff = (
        "diff --git a/a.py b/a.py\n--- a/a.py\n+++ b/a.py\n@@ -1,1 +1,2 @@\n ctx\n+new\n"
        "diff --git a/n.py b/n.py\n--- /dev/null\n+++ b/n.py\n@@ -0,0 +1,1 @@\n+added\n"
    )
    manifest = ChangeManifest(
        pr=PullRequestManifest(number=9, title="T", base="main", head="f", author="a", description="D"),
        files=[
            ChangedFileEntry(path="a.py", status=FileChangeStatus.MODIFIED),
            ChangedFileEntry(path="n.py", status=FileChangeStatus.ADDED),
        ],
        total_additions=2,
        total_deletions=0,
    )

    class FakeGit:
        def __init__(self, merge_base=ClientSuccess(data="mb123")):
            self.merge_base = merge_base
            self.fetched = []

        def fetch_refspec(self, remote, refspec):
            self.fetched.append((remote, refspec))
            return ClientSuccess(data=None)

        def get_merge_base(self, a, b):
            return self.merge_base

        def get_file_at_ref(self, ref, path):
            return ClientSuccess(data="ctx\n" if path == "a.py" else None)

    textual = SimpleNamespace(dim_text=lambda text: None)
    ctx = SimpleNamespace(git=FakeGit(), textual=textual, data={})

    result = code_review_steps._write_review_material(
        ctx, str(tmp_path), manifest, DiffContextManager.from_diff(diff), [], []
    )

    assert result == {"a.py": True, "n.py": False}
    assert ctx.git.fetched == [("origin", "+refs/heads/main:refs/titan/review/pr-9-base")]
    assert (tmp_path / ".titan-review/base/a.py").read_text() == "ctx\n"
    assert not (tmp_path / ".titan-review/base/n.py").exists()
    assert "2 [ADDED] new" in (tmp_path / ".titan-review/diffs/a.py.diff").read_text()
    assert "[ADDED] added" in (tmp_path / ".titan-review/pr.diff").read_text()
    assert "mb123" in (tmp_path / ".titan-review/pr.md").read_text()

    ctx_failing = SimpleNamespace(git=FakeGit(ClientError(error_message="no base")), textual=textual, data={})
    assert code_review_steps._write_review_material(
        ctx_failing, str(tmp_path), manifest, DiffContextManager.from_diff(diff), [], []
    ) is None
