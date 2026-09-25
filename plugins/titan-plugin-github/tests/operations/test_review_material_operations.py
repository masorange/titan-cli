"""The review material as files in the worktree: layout, content and the prompt that points at it."""

from titan_plugin_github.models.review_enums import CommentContextKind
from titan_plugin_github.models.review_models import (
    CommentContextEntry,
    FileContextEntry,
    FocusContextBatch,
    PullRequestManifest,
)
from titan_plugin_github.operations.findings_operations import build_findings_prompt_parts
from titan_plugin_github.operations.review_material_operations import (
    base_file_path,
    diff_file_path,
    render_file_diff,
    render_pr_file,
    review_material_hint,
)

PR = PullRequestManifest(
    number=7, title="Migrate API", base="main", head="feat", author="a", description="Moves X to Y."
)


def test_paths_live_in_a_hidden_folder_so_a_plain_search_skips_them():
    assert diff_file_path("src/a.py") == ".titan-review/diffs/src/a.py.diff"
    assert base_file_path("src/a.py") == ".titan-review/base/src/a.py"


def test_a_file_diff_is_numbered_like_the_prompt_was_so_anchors_still_work():
    rendered = render_file_diff("a.py", ["@@ -1,2 +1,2 @@\n context\n-old\n+new\n"])

    assert rendered.startswith("# a.py")
    assert "1 [CONTEXT] context" in rendered
    assert "[DELETED] old" in rendered
    assert "2 [ADDED] new" in rendered
    assert "(no textual diff)" in render_file_diff("img.png", [])


def test_the_pr_file_carries_the_claim_and_what_reviewers_already_said():
    comments = [
        CommentContextEntry(
            kind=CommentContextKind.COMMENT, thread_id="t", path="a.py", line=3,
            title="Crash", summary="None dereferenced", is_resolved=False,
        )
    ]

    text = render_pr_file(PR, comments, "abc123")

    assert "# PR #7: Migrate API" in text
    assert "Moves X to Y." in text
    assert "abc123" in text
    assert "- [open] a.py:3 -- Crash: None dereferenced" in text
    assert "(none)" in render_pr_file(PR, [], None)


def test_the_hint_says_whether_there_is_a_previous_version():
    assert "base: `.titan-review/base/a.py`" in review_material_hint("a.py", True)
    assert "new file (no base version)" in review_material_hint("b.py", False)


def test_with_the_material_on_disk_the_prompt_points_at_it_and_carries_no_diff():
    """The prompt went from ~400k chars of pasted diffs to a pointer per file."""
    batch = FocusContextBatch(
        batch_id="deep_1",
        change_shape=["a.py | role=business_logic | YOU: review | +1/-0"],
        comment_context=[
            CommentContextEntry(
                kind=CommentContextKind.COMMENT, thread_id="t", path="a.py", line=1,
                title="Known", summary="already said", is_resolved=False,
            )
        ],
        files_context={
            "a.py": FileContextEntry(
                path="a.py", worktree_reference=True, on_disk=True,
                review_hint=review_material_hint("a.py", True), hunks=[],
            )
        },
        pr_manifest=PR,
    )

    parts = build_findings_prompt_parts(batch)
    prompt = parts["prompt"]

    assert "## Review Material" in prompt
    assert "`.titan-review/pr.diff`" in prompt
    assert "diff: `.titan-review/diffs/a.py.diff`" in prompt
    assert "already said" not in prompt  # the comments are in pr.md
    assert "In `.titan-review/pr.md`." in prompt
    assert "[ADDED]" not in parts["files_context"]
    assert "its base version shows how it worked before" in parts["task"]
    assert "left out by rule" in prompt
    assert len(prompt) < 12_000


def test_a_removed_behaviour_is_kept_only_when_the_base_version_bears_it_out():
    """The #3723 false positive, twice: "purchase analytics are now commented out" when
    they were commented out before the PR too. The quoted old line is in both versions."""
    from titan_plugin_github.operations.review_material_operations import check_old_code_claims

    base = {
        "Screen.kt": "onSuccess = { /*viewModel.trackPurchaseEvent()*/ },\n",
        "Vm.kt": "val id = subscription.externalId\n",
    }
    head = {
        "Screen.kt": "onSuccess = { /*viewModel.trackPurchaseEvent()*/ },\n",
        "Vm.kt": "val id = subscriptionId\n",
    }
    findings = [
        {"path": "Screen.kt", "title": "analytics now commented out", "old_code": "viewModel.trackPurchaseEvent()"},
        {"path": "Vm.kt", "title": "Disney ID changed", "old_code": "val id =   subscription.externalId"},
        {"path": "Vm.kt", "title": "invented", "old_code": "showOttTransactional()"},
        {"path": "Vm.kt", "title": "no claim about the old code", "old_code": None},
    ]

    kept, rejected = check_old_code_claims(findings, base.get, head.get)

    assert [f["title"] for f in kept] == ["Disney ID changed", "no claim about the old code"]
    assert {f["title"]: f["reason"] for f in rejected} == {
        "analytics now commented out": "the old code it quotes is still in the new version",
        "invented": "the old code it quotes is not in any base version",
    }


def test_the_session_is_told_to_quote_the_old_line_when_the_material_is_on_disk():
    from titan_plugin_github.operations.findings_operations import findings_json_schema

    batch = FocusContextBatch(
        batch_id="deep_1",
        files_context={
            "a.py": FileContextEntry(path="a.py", worktree_reference=True, on_disk=True, review_hint="h")
        },
    )

    parts = build_findings_prompt_parts(batch)

    assert "puts in `old_code` the line of the base version" in parts["task"]
    assert "old_code" in findings_json_schema()["properties"]["findings"]["items"]["properties"]


def test_the_old_code_may_have_lived_in_another_changed_file():
    """#3723: `it.id != tariff.id` was dropped from two ViewModels, and the finding named the
    NEW file that replaced them, which has no base version. Checking only the finding's own
    file rejected a real defect."""
    from titan_plugin_github.operations.review_material_operations import check_old_code_claims

    base = {"ui/Vm.kt": "upgradeTariffs.filter { it.type == tariff.type && it.id != tariff.id }\n"}
    head = {"ui/Vm.kt": "deals.filter { it.isAvailableChangeFor(product) }\n", "domain/Deals.kt": "fun x()\n"}
    finding = {"path": "domain/Deals.kt", "title": "current plan no longer excluded", "old_code": "it.id != tariff.id"}

    kept, rejected = check_old_code_claims([finding], base.get, head.get, base_paths=list(base))

    assert kept == [finding] and rejected == []
