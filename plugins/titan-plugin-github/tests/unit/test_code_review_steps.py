from unittest.mock import Mock

from titan_cli.core.result import ClientSuccess
from titan_cli.engine import WorkflowContext
from titan_cli.engine.interaction.base import ItemReviewResponse
from titan_cli.engine.results import Error, Exit, Skip, Success
from titan_cli.ports.protocol import ItemReviewDecision
from titan_plugin_github.models.review_models import ChangeManifest, PullRequestManifest
from titan_plugin_github.models.review_enums import (
    FileChangeStatus,
    FindingSeverity,
    ReviewActionSource,
    ReviewActionType,
)
from titan_plugin_github.models.view import UIFileChange, UIPullRequest
from titan_plugin_github.steps.code_review_steps import (
    fetch_pr_review_bundle,
    score_review_candidates,
    validate_review_actions,
)


class _FakeTextual:
    def __init__(self):
        self.displayed_diff = None

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

    def display_diff(self, diff_text, *, title=None, metadata=None):
        self.displayed_diff = {
            "content": diff_text,
            "title": title,
            "metadata": metadata or {},
        }

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
    assert ctx.textual.displayed_diff is not None
    assert ctx.textual.displayed_diff["title"] == "Files affected:"
    assert ctx.textual.displayed_diff["metadata"]["kind"] == "unified_patch"
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


class _FakeInteraction(_FakeTextual):
    def __init__(self, responses):
        super().__init__()
        self._responses = list(responses)

    def item_review(self, interaction_id, message, state):
        self.last_item_review = {
            "interaction_id": interaction_id,
            "message": message,
            "state": state,
        }
        return self._responses.pop(0)


def _make_review_action(body: str = "Original body"):
    from titan_plugin_github.models.review_models import ReviewActionProposal

    return ReviewActionProposal(
        action_type=ReviewActionType.NEW_COMMENT,
        source=ReviewActionSource.NEW_FINDING,
        path="src/foo.py",
        line=42,
        title="Possible null handling issue",
        body=body,
        reasoning="The response may be empty here.",
        severity=FindingSeverity.IMPORTANT,
    )


def test_validate_review_actions_skips_when_no_actions():
    ctx = WorkflowContext(secrets=Mock())
    ctx.interaction = _FakeInteraction([])
    ctx.textual = ctx.interaction

    result = validate_review_actions(ctx)

    assert isinstance(result, Skip)
    assert result.message == "No actions to validate"


def test_validate_review_actions_approves_selected_actions():
    ctx = WorkflowContext(secrets=Mock())
    ctx.interaction = _FakeInteraction([ItemReviewResponse(items=[ItemReviewDecision(item_id="new_comment:0", action="approve")])])
    ctx.textual = ctx.interaction
    ctx.data["review_action_proposals"] = [_make_review_action()]
    ctx.data["review_diff"] = "@@ -1 +1 @@\n-old\n+new"
    ctx.data["review_threads"] = []

    result = validate_review_actions(ctx)

    assert isinstance(result, Success)
    approved = result.metadata["approved_action_proposals"]
    assert len(approved) == 1
    assert approved[0].body == "Original body"


def test_validate_review_actions_edits_body_when_requested():
    ctx = WorkflowContext(secrets=Mock())
    ctx.interaction = _FakeInteraction([
        ItemReviewResponse(items=[ItemReviewDecision(item_id="new_comment:0", action="edit", content="Edited body")])
    ])
    ctx.textual = ctx.interaction
    ctx.data["review_action_proposals"] = [_make_review_action()]
    ctx.data["review_diff"] = ""
    ctx.data["review_threads"] = []

    result = validate_review_actions(ctx)

    assert isinstance(result, Success)
    approved = result.metadata["approved_action_proposals"]
    assert len(approved) == 1
    assert approved[0].body == "Edited body"


def test_validate_review_actions_exits_after_partial_review():
    ctx = WorkflowContext(secrets=Mock())
    ctx.interaction = _FakeInteraction(
            [
                ItemReviewResponse(
                    items=[ItemReviewDecision(item_id="new_comment:0", action="approve")],
                    exit_requested=True,
                ),
            ]
        )
    ctx.textual = ctx.interaction
    ctx.data["review_action_proposals"] = [_make_review_action("First"), _make_review_action("Second")]
    ctx.data["review_diff"] = ""
    ctx.data["review_threads"] = []

    result = validate_review_actions(ctx)

    assert isinstance(result, Success)
    approved = result.metadata["approved_action_proposals"]
    assert len(approved) == 1
    assert approved[0].body == "First"


def test_validate_review_actions_errors_on_empty_edit_body():
    ctx = WorkflowContext(secrets=Mock())
    ctx.interaction = _FakeInteraction([
        ItemReviewResponse(items=[ItemReviewDecision(item_id="new_comment:0", action="edit", content="   ")])
    ])
    ctx.textual = ctx.interaction
    ctx.data["review_action_proposals"] = [_make_review_action()]
    ctx.data["review_diff"] = ""
    ctx.data["review_threads"] = []

    result = validate_review_actions(ctx)

    assert isinstance(result, Error)
    assert "requires non-empty content" in result.message


def test_validate_review_actions_errors_on_incomplete_non_exit_review():
    ctx = WorkflowContext(secrets=Mock())
    ctx.interaction = _FakeInteraction(
        [ItemReviewResponse(items=[ItemReviewDecision(item_id="new_comment:0", action="approve")])]
    )
    ctx.textual = ctx.interaction
    ctx.data["review_action_proposals"] = [_make_review_action("First"), _make_review_action("Second")]
    ctx.data["review_diff"] = ""
    ctx.data["review_threads"] = []

    result = validate_review_actions(ctx)

    assert isinstance(result, Error)
    assert "must include one decision for every item" in result.message


def test_validate_review_actions_errors_on_exit_action_inside_decisions():
    ctx = WorkflowContext(secrets=Mock())
    ctx.interaction = _FakeInteraction(
        [ItemReviewResponse(items=[ItemReviewDecision(item_id="new_comment:0", action="exit")])]
    )
    ctx.textual = ctx.interaction
    ctx.data["review_action_proposals"] = [_make_review_action()]
    ctx.data["review_diff"] = ""
    ctx.data["review_threads"] = []

    result = validate_review_actions(ctx)

    assert isinstance(result, Error)
    assert "exit must be expressed with exit_requested" in result.message
