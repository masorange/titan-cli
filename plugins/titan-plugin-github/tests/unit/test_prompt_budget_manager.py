"""
Baseline regression tests for `PromptBudgetManager`.

Pins the exact behavior extracted from the former free functions
`_content_budget()` (context_resolution_operations.py) and
`_fit_batch_to_budget()` (code_review_steps.py) so later heuristic changes
(worktree_reference cost penalty, per-batch limits) can be measured against
a known-good baseline.
"""

from titan_plugin_github.managers.prompt_budget_manager import (
    PromptBudgetManager,
    get_prompt_budget_manager,
)
from titan_plugin_github.models.review_enums import FileReadMode
from titan_plugin_github.models.review_models import FileContextEntry, FocusContextBatch, ReviewBudget


def make_budget(*, max_prompt_chars: int) -> ReviewBudget:
    return ReviewBudget(
        deep_files_per_session=10,
        deep_max_prompt_chars=max_prompt_chars,
        scan_max_prompt_chars=max_prompt_chars,
        scan_max_files_per_batch=12,
        max_comment_entries=5,
        deep_timeout_base_seconds=300,
        deep_timeout_per_file_seconds=120,
        deep_timeout_max_seconds=1500,
    )


def make_entry(path: str, *, chars: int, worktree_reference: bool = False) -> FileContextEntry:
    if worktree_reference:
        return FileContextEntry(
            path=path,
            read_mode=FileReadMode.WORKTREE_REFERENCE,
            worktree_reference=True,
            review_hint="Read this file from the worktree.",
            approximate_chars=chars,
        )
    return FileContextEntry(
        path=path,
        read_mode=FileReadMode.HUNKS_ONLY,
        hunks=["x" * chars],
        approximate_chars=chars,
    )


def make_batch(entries: dict[str, FileContextEntry], **overrides) -> FocusContextBatch:
    return FocusContextBatch(batch_id="batch_1", files_context=entries, **overrides)


# ---------------------------------------------------------------------------
# content_budget()
# ---------------------------------------------------------------------------


def test_content_budget_reserves_the_same_whatever_the_pr_size():
    """One reserve, not two.

    It used to reserve 5000 chars on a PR classified LARGE or HUGE and 3500 otherwise,
    which only made sense while a big PR meant more focus files. The deep tier is now
    capped at a fixed number of sessions, so the PR's overall size says nothing about how
    much room one batch needs.
    """
    manager = PromptBudgetManager()
    budget = make_budget(max_prompt_chars=20000)

    assert manager.content_budget(budget) == 20000 - manager.NON_CONTENT_RESERVE_CHARS
    assert manager.NON_CONTENT_RESERVE_CHARS == 3500


def test_content_budget_never_goes_below_floor():
    manager = PromptBudgetManager()
    budget = make_budget(max_prompt_chars=4000)

    assert manager.content_budget(budget) == 2500


def test_get_prompt_budget_manager_returns_shared_instance():
    assert get_prompt_budget_manager() is get_prompt_budget_manager()


# ---------------------------------------------------------------------------
# estimate_entry_chars()
# ---------------------------------------------------------------------------


def test_estimate_entry_chars_uses_full_content_length():
    manager = PromptBudgetManager()
    entry = FileContextEntry(path="a.py", read_mode=FileReadMode.FULL_FILE, full_content="x" * 1234)

    assert manager.estimate_entry_chars(entry) == 1234


def test_estimate_entry_chars_sums_expanded_hunks():
    manager = PromptBudgetManager()
    entry = FileContextEntry(
        path="a.py", read_mode=FileReadMode.EXPANDED_HUNKS, expanded_hunks=["x" * 100, "y" * 50]
    )

    assert manager.estimate_entry_chars(entry) == 150


def test_estimate_entry_chars_sums_hunks():
    manager = PromptBudgetManager()
    entry = FileContextEntry(path="a.py", read_mode=FileReadMode.HUNKS_ONLY, hunks=["x" * 100, "y" * 50])

    assert manager.estimate_entry_chars(entry) == 150


def test_estimate_entry_chars_charges_worktree_reference_only_for_its_prompt_text():
    """The estimate stopped standing in for the CLI's exploration cost.

    It was 5,000 chars, which forced two deep files into separate batches and so into
    separate sessions. Exploration is the session's cost, not the prompt's; the prompt's
    real size is still checked against the actual string in fit_batch_to_budget."""
    manager = PromptBudgetManager()
    entry = FileContextEntry(
        path="a.py", read_mode=FileReadMode.WORKTREE_REFERENCE, worktree_reference=True, review_hint="short"
    )

    assert manager.estimate_entry_chars(entry) == PromptBudgetManager.WORKTREE_REFERENCE_PROMPT_CHARS
    assert manager.estimate_entry_chars(entry) < 1000


def test_estimate_entry_chars_returns_zero_for_empty_entry():
    manager = PromptBudgetManager()
    entry = FileContextEntry(path="a.py")

    assert manager.estimate_entry_chars(entry) == 0


# ---------------------------------------------------------------------------
# fit_batch_to_budget()
# ---------------------------------------------------------------------------


def test_fit_batch_within_budget_is_unchanged():
    manager = PromptBudgetManager()
    batch = make_batch({"a.py": make_entry("a.py", chars=100)})
    prompt_parts = {"prompt": "x" * 100}

    fitted, changed = manager.fit_batch_to_budget(batch, prompt_parts, budget_chars=1000)

    assert changed is False
    assert len(fitted) == 1
    assert fitted[0].batch_id == "batch_1"
    assert fitted[0].prompt_actual_chars == 100


def test_fit_batch_splits_multi_file_batch_in_half():
    manager = PromptBudgetManager()
    batch = make_batch(
        {
            "a.py": make_entry("a.py", chars=100),
            "b.py": make_entry("b.py", chars=100),
            "c.py": make_entry("c.py", chars=100),
            "d.py": make_entry("d.py", chars=100),
        }
    )
    prompt_parts = {"prompt": "x" * 5000}

    fitted, changed = manager.fit_batch_to_budget(batch, prompt_parts, budget_chars=1000)

    assert changed is True
    assert len(fitted) == 2
    assert fitted[0].batch_id == "batch_1a"
    assert fitted[1].batch_id == "batch_1b"
    assert list(fitted[0].files_context.keys()) == ["a.py", "b.py"]
    assert list(fitted[1].files_context.keys()) == ["c.py", "d.py"]
    assert fitted[0].degraded_context is True
    assert fitted[1].degraded_context is True


def test_fit_batch_degrades_single_file_to_worktree_reference():
    manager = PromptBudgetManager()
    batch = make_batch({"a.py": make_entry("a.py", chars=100)})
    prompt_parts = {"prompt": "x" * 5000}

    fitted, changed = manager.fit_batch_to_budget(batch, prompt_parts, budget_chars=1000)

    assert changed is True
    assert len(fitted) == 1
    entry = fitted[0].files_context["a.py"]
    assert entry.worktree_reference is True
    assert entry.read_mode == FileReadMode.WORKTREE_REFERENCE
    assert entry.full_content is None
    assert entry.approximate_chars <= 800
    assert fitted[0].degraded_context is True


def test_fit_batch_never_degrades_to_worktree_reference_when_reads_not_allowed():
    """allow_file_reads=False means the checkout is not provably the PR's revision —
    the wrong-revision guard already refused worktree_reference at context resolution,
    so the budget-fitting pass must not reintroduce it through the back door."""
    manager = PromptBudgetManager()
    batch = make_batch({"a.py": make_entry("a.py", chars=100)})
    prompt_parts = {"prompt": "x" * 5000}

    fitted, changed = manager.fit_batch_to_budget(
        batch, prompt_parts, budget_chars=1000, allow_file_reads=False
    )

    assert len(fitted) == 1
    entry = fitted[0].files_context["a.py"]
    assert entry.worktree_reference is False
    assert entry.read_mode != FileReadMode.WORKTREE_REFERENCE
    # With nothing else to trim, the batch reports oversized instead.
    assert fitted[0].prompt_still_too_large is True


def test_fit_batch_drops_related_files_when_only_worktree_reference_left():
    manager = PromptBudgetManager()
    batch = make_batch(
        {"a.py": make_entry("a.py", chars=100, worktree_reference=True)},
        related_files={"b.py": "some related content"},
    )
    prompt_parts = {"prompt": "x" * 5000}

    fitted, changed = manager.fit_batch_to_budget(batch, prompt_parts, budget_chars=1000)

    assert changed is True
    assert fitted[0].related_files == {}
    assert fitted[0].degraded_context is True


def test_fit_batch_drops_comment_context_when_related_files_already_empty():
    from titan_plugin_github.models.review_enums import CommentContextKind
    from titan_plugin_github.models.review_models import CommentContextEntry

    manager = PromptBudgetManager()
    batch = make_batch(
        {"a.py": make_entry("a.py", chars=100, worktree_reference=True)},
        comment_context=[
            CommentContextEntry(kind=CommentContextKind.COMMENT, thread_id="t1", path="a.py", summary="hi")
        ],
    )
    prompt_parts = {"prompt": "x" * 5000}

    fitted, changed = manager.fit_batch_to_budget(batch, prompt_parts, budget_chars=1000)

    assert changed is True
    assert fitted[0].comment_context == []
    assert fitted[0].degraded_context is True


def test_fit_batch_marks_oversized_when_nothing_left_to_trim():
    manager = PromptBudgetManager()
    batch = make_batch({"a.py": make_entry("a.py", chars=100, worktree_reference=True)})
    prompt_parts = {"prompt": "x" * 5000}

    fitted, changed = manager.fit_batch_to_budget(batch, prompt_parts, budget_chars=1000)

    assert changed is False
    assert len(fitted) == 1
    assert fitted[0].prompt_still_too_large is True
    assert fitted[0].prompt_actual_chars == 5000
    assert fitted[0].degraded_context is True


# ---------------------------------------------------------------------------
# Single-file hunk splitting (last resort before oversized)
# ---------------------------------------------------------------------------


def test_fit_batch_splits_one_files_hunks_when_no_other_degradation_is_left():
    """The shape that actually broke: one file whose own hunks exceed the budget.

    Splitting by file does nothing there. Measured on PR #254, one file with 22 hunks
    built a 149,353-char prompt against an 18,000 budget and the batch was skipped
    rather than divided, so the PR's main file went unreviewed three runs in a row.
    """
    manager = PromptBudgetManager()
    entry = FileContextEntry(
        path="a.py",
        read_mode=FileReadMode.HUNKS_ONLY,
        hunks=[f"hunk-{index}" for index in range(4)],
        approximate_chars=4000,
    )
    batch = make_batch({"a.py": entry})

    fitted, changed = manager.fit_batch_to_budget(
        batch, {"prompt": "x" * 5000}, budget_chars=1000, allow_file_reads=False
    )

    assert changed is True
    assert [candidate.batch_id for candidate in fitted] == ["batch_1a", "batch_1b"]
    assert fitted[0].files_context["a.py"].hunks == ["hunk-0", "hunk-1"]
    assert fitted[1].files_context["a.py"].hunks == ["hunk-2", "hunk-3"]
    # Every hunk survives the split: the point is to review all of them, in more calls.
    assert all(candidate.degraded_context for candidate in fitted)
    assert fitted[0].files_context["a.py"].approximate_chars == len("hunk-0") + len("hunk-1")


def test_fit_batch_reports_oversized_when_a_single_hunk_exceeds_the_budget():
    """One hunk is indivisible, so this still reports oversized — but the caller now
    says so out loud instead of dropping the batch silently."""
    manager = PromptBudgetManager()
    batch = make_batch({"a.py": make_entry("a.py", chars=5000)})

    fitted, changed = manager.fit_batch_to_budget(
        batch, {"prompt": "x" * 5000}, budget_chars=1000, allow_file_reads=False
    )

    assert changed is False
    assert fitted[0].prompt_still_too_large is True


def test_fit_batch_prefers_worktree_reference_over_splitting_hunks():
    """Hunk splitting is the LAST resort: when reading the file is allowed, one call
    that reads it beats two calls that each see half the diff."""
    manager = PromptBudgetManager()
    entry = FileContextEntry(
        path="a.py",
        read_mode=FileReadMode.HUNKS_ONLY,
        hunks=[f"hunk-{index}" for index in range(4)],
        approximate_chars=4000,
    )
    batch = make_batch({"a.py": entry})

    fitted, changed = manager.fit_batch_to_budget(
        batch, {"prompt": "x" * 5000}, budget_chars=1000, allow_file_reads=True
    )

    assert changed is True
    assert len(fitted) == 1
    assert fitted[0].files_context["a.py"].worktree_reference is True


def test_fit_batch_drops_the_inline_diff_before_giving_up_on_a_worktree_file():
    """A NEW file is one single hunk, so there is nothing to split — and skipping it is
    the worst outcome available.

    Measured on PR 251: locks.py (+323) and models.py (+301) arrived as one ~12k-char hunk
    each and were reported "too large even after reduction. NOT reviewed". The reference
    survives without the diff: the session opens the file from the working tree and the
    hunk headers still say which regions changed."""
    manager = PromptBudgetManager()
    entry = FileContextEntry(
        path="locks.py",
        read_mode=FileReadMode.WORKTREE_REFERENCE,
        worktree_reference=True,
        hunks=["@@ -0,0 +1,323 @@\n" + "+line\n" * 323],
        changed_hunk_headers=["@@ -0,0 +1,323 @@"],
        review_hint="Central changed file.",
    )
    batch = make_batch({"locks.py": entry})

    fitted, changed = manager.fit_batch_to_budget(
        batch, {"prompt": "x" * 20000}, budget_chars=1000, allow_file_reads=False
    )

    assert changed is True
    assert len(fitted) == 1
    survivor = fitted[0].files_context["locks.py"]
    assert survivor.hunks == []
    assert survivor.worktree_reference is True
    assert survivor.changed_hunk_headers == ["@@ -0,0 +1,323 @@"]
