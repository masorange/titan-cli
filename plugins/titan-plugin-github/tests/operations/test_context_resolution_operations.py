"""
Baseline regression test proving `build_review_context_package()` batches files
according to `PromptBudgetManager.content_budget()` (review-batching-003
extraction). Guards against silently reverting to the old inline
`_content_budget()` free function.
"""

from titan_plugin_github.models.review_enums import ChecklistCategory, FileChangeStatus, FileReadMode, FileReviewPriority, PRSizeClass, ReviewStrategyType
from titan_plugin_github.models.review_models import (
    ChangeManifest,
    ChangedFileEntry,
    FileReviewPlan,
    PullRequestManifest,
    ReviewChecklistItem,
    ReviewPlan,
    ReviewStrategy,
)
from titan_plugin_github.operations.context_resolution_operations import build_review_context_package


def make_diff(path: str, added_line: str) -> str:
    return (
        f"diff --git a/{path} b/{path}\n"
        f"index abc..def 100644\n"
        f"--- a/{path}\n"
        f"+++ b/{path}\n"
        f"@@ -1,1 +1,2 @@\n"
        f" context line\n"
        f"+{added_line}\n"
    )


def make_manifest(paths: list[str]) -> ChangeManifest:
    files = [
        ChangedFileEntry(path=path, status=FileChangeStatus.MODIFIED, additions=1, deletions=0) for path in paths
    ]
    return ChangeManifest(
        pr=PullRequestManifest(number=1, title="Test PR", base="main", head="feat/test", author="alex", description=""),
        files=files,
        total_additions=len(files),
        total_deletions=0,
    )


def test_build_review_context_package_batches_by_manager_content_budget():
    paths = ["a.py", "b.py", "c.py"]
    diff = "".join(make_diff(path, "x" * 3000) for path in paths)
    plan = ReviewPlan(
        focus_files=[
            FileReviewPlan(path=path, priority=FileReviewPriority.HIGH, read_mode=FileReadMode.HUNKS_ONLY)
            for path in paths
        ],
        review_axes=[ChecklistCategory.FUNCTIONAL_CORRECTNESS],
    )
    manifest = make_manifest(paths)
    checklist = [
        ReviewChecklistItem(
            id=ChecklistCategory.FUNCTIONAL_CORRECTNESS,
            name="Functional correctness",
            description="Does it work",
        )
    ]
    strategy = ReviewStrategy(
        strategy=ReviewStrategyType.BATCHED_FINDINGS,
        size_class=PRSizeClass.SMALL,
        max_focus_files=10,
        max_prompt_chars=4000,
        max_comment_entries=5,
        batching_enabled=True,
    )

    package = build_review_context_package(plan, diff, manifest, checklist, comment_context=[], strategy=strategy)

    # content_budget(strategy) == max(2500, 4000 - 3500) == 2500; each ~3000-char
    # hunk alone exceeds that budget, so every file must land in its own batch.
    assert len(package.batches) == 3
    assert [batch.batch_id for batch in package.batches] == ["batch_1", "batch_2", "batch_3"]
    assert [list(batch.files_context.keys()) for batch in package.batches] == [["a.py"], ["b.py"], ["c.py"]]


def test_build_review_context_package_keeps_small_files_in_one_batch():
    paths = ["a.py", "b.py", "c.py"]
    diff = "".join(make_diff(path, "x" * 10) for path in paths)
    plan = ReviewPlan(
        focus_files=[
            FileReviewPlan(path=path, priority=FileReviewPriority.HIGH, read_mode=FileReadMode.HUNKS_ONLY)
            for path in paths
        ],
        review_axes=[ChecklistCategory.FUNCTIONAL_CORRECTNESS],
    )
    manifest = make_manifest(paths)
    checklist = [
        ReviewChecklistItem(
            id=ChecklistCategory.FUNCTIONAL_CORRECTNESS,
            name="Functional correctness",
            description="Does it work",
        )
    ]
    strategy = ReviewStrategy(
        strategy=ReviewStrategyType.BATCHED_FINDINGS,
        size_class=PRSizeClass.SMALL,
        max_focus_files=10,
        max_prompt_chars=20000,
        max_comment_entries=5,
        batching_enabled=True,
    )

    package = build_review_context_package(plan, diff, manifest, checklist, comment_context=[], strategy=strategy)

    assert len(package.batches) == 1
    assert set(package.batches[0].files_context.keys()) == set(paths)
