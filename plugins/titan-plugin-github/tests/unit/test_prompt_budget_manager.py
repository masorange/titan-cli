from titan_plugin_github.managers.prompt_budget_manager import PromptBudgetManager
from titan_plugin_github.models.review_enums import (
    CommentContextKind,
    FileReadMode,
    PRSizeClass,
    ReviewStrategyType,
)
from titan_plugin_github.models.review_models import (
    CommentContextEntry,
    FileContextEntry,
    FocusContextBatch,
    ReviewStrategy,
)


def make_strategy(*, size_class: PRSizeClass = PRSizeClass.SMALL, max_prompt_chars: int = 22000) -> ReviewStrategy:
    return ReviewStrategy(
        strategy=ReviewStrategyType.DIRECT_FINDINGS,
        size_class=size_class,
        max_focus_files=4,
        max_prompt_chars=max_prompt_chars,
        max_comment_entries=8,
        batching_enabled=size_class in {PRSizeClass.LARGE, PRSizeClass.HUGE},
    )


def make_batch(
    *,
    batch_id: str = "batch_1",
    files_context: dict[str, FileContextEntry] | None = None,
    related_files: dict[str, str] | None = None,
    comment_context: list[CommentContextEntry] | None = None,
) -> FocusContextBatch:
    return FocusContextBatch(
        batch_id=batch_id,
        files_context=files_context or {},
        related_files=related_files or {},
        comment_context=comment_context or [],
    )


def make_comment() -> CommentContextEntry:
    return CommentContextEntry(
        kind=CommentContextKind.COMMENT,
        thread_id="t1",
        path="src/foo.py",
        line=10,
        title="Existing thread",
        summary="Already discussed",
        is_resolved=False,
    )


def test_fit_findings_batch_to_budget_keeps_batch_when_prompt_already_fits():
    manager = PromptBudgetManager()
    batch = make_batch(files_context={"src/foo.py": FileContextEntry(path="src/foo.py")})

    result = manager.fit_findings_batch_to_budget(batch, {"prompt": "x" * 120}, budget_chars=200)

    assert result.changed is False
    assert len(result.batches) == 1
    assert result.batches[0].batch_id == "batch_1"
    assert result.batches[0].prompt_actual_chars == 120
    assert result.batches[0].degraded_context is False


def test_fit_findings_batch_to_budget_splits_multi_file_batch():
    manager = PromptBudgetManager()
    batch = make_batch(
        files_context={
            "src/a.py": FileContextEntry(path="src/a.py"),
            "src/b.py": FileContextEntry(path="src/b.py"),
        }
    )

    result = manager.fit_findings_batch_to_budget(batch, {"prompt": "x" * 500}, budget_chars=200)

    assert result.changed is True
    assert [item.batch_id for item in result.batches] == ["batch_1a", "batch_1b"]
    assert list(result.batches[0].files_context.keys()) == ["src/a.py"]
    assert list(result.batches[1].files_context.keys()) == ["src/b.py"]
    assert all(item.degraded_context for item in result.batches)


def test_fit_findings_batch_to_budget_degrades_single_file_to_worktree_reference():
    manager = PromptBudgetManager()
    batch = make_batch(
        files_context={
            "src/foo.py": FileContextEntry(
                path="src/foo.py",
                read_mode=FileReadMode.FULL_FILE,
                full_content="print('x')",
                expanded_hunks=["@@ -1 +1 @@\n+print('x')"],
                hunks=["@@ -1 +1 @@\n+print('x')"],
                changed_hunk_headers=["@@ -1 +1 @@"],
                approximate_chars=1200,
            )
        }
    )

    result = manager.fit_findings_batch_to_budget(batch, {"prompt": "x" * 500}, budget_chars=200)

    assert result.changed is True
    degraded = result.batches[0]
    entry = degraded.files_context["src/foo.py"]
    assert degraded.degraded_context is True
    assert entry.full_content is None
    assert entry.expanded_hunks == []
    assert entry.hunks == []
    assert entry.read_mode == FileReadMode.WORKTREE_REFERENCE
    assert entry.worktree_reference is True
    assert entry.changed_hunk_headers == ["@@ -1 +1 @@"]


def test_fit_findings_batch_to_budget_removes_related_files_after_worktree_reference():
    manager = PromptBudgetManager()
    batch = make_batch(
        files_context={
            "src/foo.py": FileContextEntry(
                path="src/foo.py",
                read_mode=FileReadMode.WORKTREE_REFERENCE,
                worktree_reference=True,
            )
        },
        related_files={"test": "x" * 100},
    )

    result = manager.fit_findings_batch_to_budget(batch, {"prompt": "x" * 500}, budget_chars=200)

    assert result.changed is True
    assert result.batches[0].related_files == {}
    assert result.batches[0].degraded_context is True


def test_fit_findings_batch_to_budget_removes_comment_context_after_related_files():
    manager = PromptBudgetManager()
    batch = make_batch(
        files_context={
            "src/foo.py": FileContextEntry(
                path="src/foo.py",
                read_mode=FileReadMode.WORKTREE_REFERENCE,
                worktree_reference=True,
            )
        },
        comment_context=[make_comment()],
    )

    result = manager.fit_findings_batch_to_budget(batch, {"prompt": "x" * 500}, budget_chars=200)

    assert result.changed is True
    assert result.batches[0].comment_context == []
    assert result.batches[0].degraded_context is True


def test_fit_findings_batch_to_budget_marks_batch_oversized_when_no_more_degradation_is_possible():
    manager = PromptBudgetManager()
    batch = make_batch(
        files_context={
            "src/foo.py": FileContextEntry(
                path="src/foo.py",
                read_mode=FileReadMode.WORKTREE_REFERENCE,
                worktree_reference=True,
            )
        }
    )

    result = manager.fit_findings_batch_to_budget(batch, {"prompt": "x" * 500}, budget_chars=200)

    assert result.changed is False
    oversized = result.batches[0]
    assert oversized.prompt_still_too_large is True
    assert oversized.prompt_actual_chars == 500
    assert oversized.degraded_context is True


def test_content_budget_for_strategy_preserves_small_pr_reserve():
    manager = PromptBudgetManager()
    strategy = make_strategy(size_class=PRSizeClass.SMALL, max_prompt_chars=22000)

    assert manager.content_budget_for_strategy(strategy) == 18500


def test_content_budget_for_strategy_preserves_large_pr_reserve():
    manager = PromptBudgetManager()
    strategy = make_strategy(size_class=PRSizeClass.LARGE, max_prompt_chars=24000)

    assert manager.content_budget_for_strategy(strategy) == 19000


def test_content_budget_for_strategy_keeps_minimum_floor():
    manager = PromptBudgetManager()
    strategy = make_strategy(size_class=PRSizeClass.HUGE, max_prompt_chars=6000)

    assert manager.content_budget_for_strategy(strategy) == 2500
