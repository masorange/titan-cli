"""
Baseline regression test proving `build_review_context_package()` batches files
according to `PromptBudgetManager.content_budget()` (review-batching-003
extraction). Guards against silently reverting to the old inline
`_content_budget()` free function.
"""

from titan_plugin_github.managers.prompt_budget_manager import get_prompt_budget_manager
from titan_plugin_github.models.review_enums import (
    AttentionTier,
    ChecklistCategory,
    ContextRequestType,
    FileChangeStatus,
    FileReadMode,
    FileReviewPriority,
)
from titan_plugin_github.models.review_models import (
    ChangeManifest,
    ChangedFileEntry,
    ContextRequest,
    FileReviewPlan,
    PullRequestManifest,
    ReviewChecklistItem,
    ReviewPlan,
    ReviewBudget,
)
from titan_plugin_github.operations.context_resolution_operations import (
    build_review_context_package,
    resolve_file_read_access,
)


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


def test_deep_files_are_one_batch_whatever_their_size():
    """The deep tier is ONE session. The character budget no longer decides how many AI
    calls a review makes.

    This replaces a test that pinned the opposite: three ~3000-char files against a
    2,500-char content budget produced three batches, one per file. That packer made the
    call count an accident of file size — nine deep files became seven calls on PR 251 —
    and made the attention tiers decoration, since a character sum was what actually
    decided the work. What the budget still decides is how much of each file's diff
    travels inline."""
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
    budget = ReviewBudget(
        deep_files_per_session=10,
        deep_max_prompt_chars=4000,
        scan_max_prompt_chars=4000,
        scan_max_files_per_batch=12,
        max_comment_entries=5,
        deep_timeout_base_seconds=300,
        deep_timeout_per_file_seconds=120,
        deep_timeout_max_seconds=1500,
    )

    package = build_review_context_package(plan, diff, manifest, checklist, comment_context=[], budget=budget)

    assert len(package.batches) == 1
    assert package.batches[0].batch_id == "deep_1"
    assert package.batches[0].tier == AttentionTier.DEEP
    assert list(package.batches[0].files_context.keys()) == paths


def test_no_deep_file_is_dropped_at_packaging_time():
    """Coverage is never lost while building the context: every focus file is in the
    batch, whatever it resolved to."""
    paths = ["big_first.py", "second.py"]
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
    budget = ReviewBudget(
        deep_files_per_session=4,
        deep_max_prompt_chars=4000,
        scan_max_prompt_chars=4000,
        scan_max_files_per_batch=12,
        max_comment_entries=5,
        deep_timeout_base_seconds=300,
        deep_timeout_per_file_seconds=120,
        deep_timeout_max_seconds=1500,
    )

    package = build_review_context_package(plan, diff, manifest, checklist, comment_context=[], budget=budget)

    reviewed_paths = {path for batch in package.batches for path in batch.files_context}
    assert reviewed_paths == set(paths)
    assert len(package.batches) == 1


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
    budget = ReviewBudget(
        deep_files_per_session=10,
        deep_max_prompt_chars=20000,
        scan_max_prompt_chars=20000,
        scan_max_files_per_batch=12,
        max_comment_entries=5,
        deep_timeout_base_seconds=300,
        deep_timeout_per_file_seconds=120,
        deep_timeout_max_seconds=1500,
    )

    package = build_review_context_package(plan, diff, manifest, checklist, comment_context=[], budget=budget)

    assert len(package.batches) == 1
    assert set(package.batches[0].files_context.keys()) == set(paths)


def test_worktree_reference_entries_cost_only_what_they_occupy_in_the_prompt():
    """A worktree_reference entry is a path, a hint and the hunk headers — a few hundred
    chars — and that is all it is charged.

    It used to be charged 5,000 to stand in for the CLI's exploration cost. That
    inflation, together with the one-per-batch rule deleted below, is why nine deep files
    meant nine AI calls: measured on PR 251, $7.4581 and 100,365 output tokens across nine
    calls with zero cache, against $2.5215 and 25,874 for one session over the same files.
    Exploration is not paid in prompt characters."""
    paths = ["a.py", "b.py"]
    diff = "".join(make_diff(path, "x" * 10) for path in paths)
    plan = ReviewPlan(
        focus_files=[
            FileReviewPlan(path=path, priority=FileReviewPriority.HIGH, read_mode=FileReadMode.WORKTREE_REFERENCE)
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
    # A budget that the old 5,000-char estimate would have split; two honest entries fit.
    budget = ReviewBudget(
        deep_files_per_session=10,
        deep_max_prompt_chars=6000,
        scan_max_prompt_chars=6000,
        scan_max_files_per_batch=12,
        max_comment_entries=5,
        deep_timeout_base_seconds=300,
        deep_timeout_per_file_seconds=120,
        deep_timeout_max_seconds=1500,
    )

    package = build_review_context_package(plan, diff, manifest, checklist, comment_context=[], budget=budget)

    first_entry = package.batches[0].files_context["a.py"]
    assert first_entry.worktree_reference is True
    assert first_entry.approximate_chars == get_prompt_budget_manager().WORKTREE_REFERENCE_PROMPT_CHARS
    assert len(package.batches) == 1
    assert list(package.batches[0].files_context.keys()) == ["a.py", "b.py"]


def test_every_deep_file_lands_in_one_batch_when_the_budget_allows():
    """The deep tier is ONE session over the files that matter.

    This replaces review-batching-005, which pinned the opposite: at most one
    worktree_reference file per batch, on the theory that each one means another full file
    read by the CLI. It does — but that cost is the session's, not the prompt's, and
    paying it once per file bought nine independent analyses that could not share a cache
    or see each other's files."""
    paths = ["a.py", "b.py", "c.py"]
    diff = "".join(make_diff(path, "x" * 10) for path in paths)
    plan = ReviewPlan(
        focus_files=[
            FileReviewPlan(path=path, priority=FileReviewPriority.HIGH, read_mode=FileReadMode.WORKTREE_REFERENCE)
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
    budget = ReviewBudget(
        deep_files_per_session=10,
        deep_max_prompt_chars=100_000,
        scan_max_prompt_chars=100_000,
        scan_max_files_per_batch=12,
        max_comment_entries=5,
        deep_timeout_base_seconds=300,
        deep_timeout_per_file_seconds=120,
        deep_timeout_max_seconds=1500,
    )

    package = build_review_context_package(plan, diff, manifest, checklist, comment_context=[], budget=budget)

    assert len(package.batches) == 1
    assert list(package.batches[0].files_context.keys()) == paths


def test_inline_and_worktree_reference_files_share_one_batch():
    """Mixed read modes are one session too: the char budget is now the only thing that
    starts a new batch."""
    plan = ReviewPlan(
        focus_files=[
            FileReviewPlan(path="inline.py", priority=FileReviewPriority.HIGH, read_mode=FileReadMode.HUNKS_ONLY),
            FileReviewPlan(path="a.py", priority=FileReviewPriority.HIGH, read_mode=FileReadMode.WORKTREE_REFERENCE),
            FileReviewPlan(path="b.py", priority=FileReviewPriority.HIGH, read_mode=FileReadMode.WORKTREE_REFERENCE),
        ],
        review_axes=[ChecklistCategory.FUNCTIONAL_CORRECTNESS],
    )
    diff = "".join(make_diff(path, "x" * 10) for path in ["inline.py", "a.py", "b.py"])
    manifest = make_manifest(["inline.py", "a.py", "b.py"])
    checklist = [
        ReviewChecklistItem(
            id=ChecklistCategory.FUNCTIONAL_CORRECTNESS,
            name="Functional correctness",
            description="Does it work",
        )
    ]
    budget = ReviewBudget(
        deep_files_per_session=10,
        deep_max_prompt_chars=100_000,
        scan_max_prompt_chars=100_000,
        scan_max_files_per_batch=12,
        max_comment_entries=5,
        deep_timeout_base_seconds=300,
        deep_timeout_per_file_seconds=120,
        deep_timeout_max_seconds=1500,
    )

    package = build_review_context_package(plan, diff, manifest, checklist, comment_context=[], budget=budget)

    assert len(package.batches) == 1
    assert list(package.batches[0].files_context.keys()) == ["inline.py", "a.py", "b.py"]



# ---------------------------------------------------------------------------
# File-read access: never pair the PR's diff with another revision's file content
# ---------------------------------------------------------------------------

HEAD_SHA = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
OTHER_SHA = "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"


class TestResolveFileReadAccess:
    def test_worktree_is_always_trusted(self):
        access = resolve_file_read_access("/tmp/titan-review-1")

        assert access.allowed is True
        assert access.source == "worktree"

    def test_worktree_does_not_need_sha_verification(self):
        """The worktree is checked out at the PR ref, so a mismatching local
        checkout is irrelevant."""
        access = resolve_file_read_access(
            "/tmp/titan-review-1", head_sha=HEAD_SHA, checkout_sha=OTHER_SHA, checkout_dirty=True
        )

        assert access.allowed is True

    def test_clean_checkout_at_head_is_trusted(self):
        access = resolve_file_read_access(
            None, head_sha=HEAD_SHA, checkout_sha=HEAD_SHA, checkout_dirty=False
        )

        assert access.allowed is True
        assert access.source == "checkout"

    def test_checkout_on_another_revision_is_rejected(self):
        """The bug this guards: worktree creation failed, the user is on another
        branch, and full-file reads would review code that is not in the PR."""
        access = resolve_file_read_access(
            None, head_sha=HEAD_SHA, checkout_sha=OTHER_SHA, checkout_dirty=False
        )

        assert access.allowed is False
        assert access.source == "none"
        assert "aaaaaaaa" in access.reason and "bbbbbbbb" in access.reason

    def test_dirty_checkout_at_head_is_rejected(self):
        access = resolve_file_read_access(
            None, head_sha=HEAD_SHA, checkout_sha=HEAD_SHA, checkout_dirty=True
        )

        assert access.allowed is False
        assert "uncommitted" in access.reason

    def test_unverifiable_dirty_state_at_head_is_rejected(self):
        access = resolve_file_read_access(
            None, head_sha=HEAD_SHA, checkout_sha=HEAD_SHA, checkout_dirty=None
        )

        assert access.allowed is False
        assert access.source == "none"
        assert "could not be verified" in access.reason

    def test_unknown_checkout_sha_is_rejected(self):
        access = resolve_file_read_access(None, head_sha=HEAD_SHA, checkout_sha=None)

        assert access.allowed is False

    def test_unknown_head_sha_is_rejected(self):
        access = resolve_file_read_access(None, head_sha=None, checkout_sha=HEAD_SHA)

        assert access.allowed is False

    def test_no_information_at_all_is_rejected(self):
        assert resolve_file_read_access(None).allowed is False


def _single_file_setup(read_mode, path="a.py"):
    diff = make_diff(path, "added_line = 1")
    plan = ReviewPlan(
        focus_files=[
            FileReviewPlan(path=path, priority=FileReviewPriority.HIGH, read_mode=read_mode)
        ],
        review_axes=[ChecklistCategory.FUNCTIONAL_CORRECTNESS],
    )
    checklist = [
        ReviewChecklistItem(
            id=ChecklistCategory.FUNCTIONAL_CORRECTNESS,
            name="Functional correctness",
            description="Does it work",
        )
    ]
    budget = ReviewBudget(
        deep_files_per_session=10,
        deep_max_prompt_chars=100_000,
        scan_max_prompt_chars=100_000,
        scan_max_files_per_batch=12,
        max_comment_entries=5,
        deep_timeout_base_seconds=300,
        deep_timeout_per_file_seconds=120,
        deep_timeout_max_seconds=1500,
    )
    return diff, plan, make_manifest([path]), checklist, budget


class TestBuildPackageWithoutFileReads:
    def test_full_file_degrades_to_hunks_only(self, tmp_path):
        """A real file exists at cwd, but it is the wrong revision — it must be ignored."""
        (tmp_path / "a.py").write_text("content from the wrong branch\n" * 5)
        diff, plan, manifest, checklist, budget = _single_file_setup(FileReadMode.FULL_FILE)

        package = build_review_context_package(
            plan, diff, manifest, checklist,
            comment_context=[], budget=budget,
            cwd=str(tmp_path), allow_file_reads=False,
        )

        entry = package.batches[0].files_context["a.py"]
        assert entry.read_mode == FileReadMode.HUNKS_ONLY
        assert entry.full_content is None
        assert "wrong branch" not in "".join(entry.hunks)

    def test_expanded_hunks_degrades_to_hunks_only(self, tmp_path):
        (tmp_path / "a.py").write_text("content from the wrong branch\n" * 5)
        diff, plan, manifest, checklist, budget = _single_file_setup(FileReadMode.EXPANDED_HUNKS)

        package = build_review_context_package(
            plan, diff, manifest, checklist,
            comment_context=[], budget=budget,
            cwd=str(tmp_path), allow_file_reads=False,
        )

        entry = package.batches[0].files_context["a.py"]
        assert entry.read_mode == FileReadMode.HUNKS_ONLY
        assert entry.expanded_hunks == []

    def test_a_readable_file_becomes_a_reference_plus_its_diff(self, tmp_path):
        """With the working tree trusted, the file body stays on disk and the prompt
        carries the diff.

        It used to inline the whole file. On PR 251 that filled the content budget with
        bodies the session could have opened itself, spilling nine deep files into seven
        batches — and Phase 1 then stripped those bodies to make each call fit, so the
        batch count was decided on a size the prompt never had."""
        (tmp_path / "a.py").write_text("verified content\n")
        diff, plan, manifest, checklist, budget = _single_file_setup(FileReadMode.FULL_FILE)

        package = build_review_context_package(
            plan, diff, manifest, checklist,
            comment_context=[], budget=budget,
            cwd=str(tmp_path), allow_file_reads=True,
        )

        entry = package.batches[0].files_context["a.py"]
        assert entry.read_mode == FileReadMode.WORKTREE_REFERENCE
        assert entry.worktree_reference is True
        assert entry.full_content is None
        assert entry.hunks  # the diff still travels, for anchoring

    def test_never_falls_back_to_worktree_reference(self):
        """worktree_reference has the CLI read the file itself — the same
        wrong-revision read, just delegated."""
        path = "big.py"
        diff, plan, manifest, checklist, budget = _single_file_setup(
            FileReadMode.FULL_FILE, path=path
        )
        # Oversized hunk: normally this ends up as a worktree_reference entry.
        diff = make_diff(path, "x" * 40_000)

        package = build_review_context_package(
            plan, diff, manifest, checklist,
            comment_context=[], budget=budget,
            allow_file_reads=False,
        )

        entry = package.batches[0].files_context[path]
        assert entry.worktree_reference is False
        assert entry.read_mode == FileReadMode.HUNKS_ONLY

    def test_file_absent_from_diff_gets_headers_only_with_a_hint(self):
        diff, plan, manifest, checklist, budget = _single_file_setup(
            FileReadMode.FULL_FILE, path="in_plan.py"
        )
        diff = make_diff("something_else.py", "y = 2")

        package = build_review_context_package(
            plan, diff, manifest, checklist,
            comment_context=[], budget=budget,
            allow_file_reads=False,
        )

        entry = package.batches[0].files_context["in_plan.py"]
        assert entry.worktree_reference is False
        assert entry.hunks == []
        assert "not at this PR's head commit" in entry.review_hint

    def test_related_context_requests_are_skipped(self, tmp_path):
        (tmp_path / "test_a.py").write_text("def test_something(): pass\n")
        diff, plan, manifest, checklist, budget = _single_file_setup(FileReadMode.HUNKS_ONLY)
        plan = ReviewPlan(
            focus_files=plan.focus_files,
            review_axes=plan.review_axes,
            extra_context_requests=[
                ContextRequest(type=ContextRequestType.RELATED_TESTS, for_path="a.py")
            ],
        )

        package = build_review_context_package(
            plan, diff, manifest, checklist,
            comment_context=[], budget=budget,
            cwd=str(tmp_path), allow_file_reads=False,
        )

        assert package.batches[0].related_files == {}


# ---------------------------------------------------------------------------
# Related context: a pointer when the tree is readable, content when it is not
# ---------------------------------------------------------------------------


def test_related_context_is_a_pointer_when_the_working_tree_is_readable(tmp_path):
    """The session can open a sibling file itself, so it is named, not pasted.

    Pasting it cost up to 2,000 chars of the content budget and was charged to EVERY
    batch (related context ships with all of them), only to be stripped again by the
    first degradation that made a call fit."""
    from titan_plugin_github.models.review_enums import ContextRequestType
    from titan_plugin_github.models.review_models import ContextRequest
    from titan_plugin_github.operations.context_resolution_operations import (
        resolve_context_requests,
    )

    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "__init__.py").write_text("SECRET_SENTINEL = 1\n")

    resolved = resolve_context_requests(
        [ContextRequest(type=ContextRequestType.RELATED_CONTEXT, for_path="pkg/mod.py")],
        cwd=str(tmp_path),
        allow_file_reads=True,
    )

    value = next(iter(resolved.values()))
    assert "pkg/__init__.py" in value
    assert "SECRET_SENTINEL" not in value
    assert "\n" not in value


def test_related_context_is_empty_when_files_may_not_be_read(tmp_path):
    """Unchanged: an unverified checkout must never put another revision's code in the
    prompt, and a pointer to it would be just as wrong."""
    from titan_plugin_github.models.review_enums import ContextRequestType
    from titan_plugin_github.models.review_models import ContextRequest
    from titan_plugin_github.operations.context_resolution_operations import (
        resolve_context_requests,
    )

    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "__init__.py").write_text("x = 1\n")

    assert (
        resolve_context_requests(
            [ContextRequest(type=ContextRequestType.RELATED_CONTEXT, for_path="pkg/mod.py")],
            cwd=str(tmp_path),
            allow_file_reads=False,
        )
        == {}
    )


def test_only_deep_tier_files_reach_the_review_session():
    """The deep session reads the deep files and nothing else.

    `focus_files` came straight from the scorer, so a file the attention plan had tiered
    `glance` or `skip` could still be deep-read: on PR 251 `docs/concepts/oauth-manager.md`
    was tiered skip and went into a review batch anyway, which made the tiers decoration.
    """
    from titan_plugin_github.models.review_enums import AttentionTier
    from titan_plugin_github.operations.attention_operations import AttentionPlan, FileAttention

    paths = ["core.py", "ui.py", "notes.md"]
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
    attention_plan = AttentionPlan(
        files=[
            FileAttention("core.py", AttentionTier.DEEP, "business_logic", "role"),
            FileAttention("ui.py", AttentionTier.GLANCE, "entrypoints_or_ui", "role"),
            FileAttention("notes.md", AttentionTier.SKIP, "docs_or_generated", "role"),
        ]
    )
    budget = ReviewBudget(
        deep_files_per_session=10,
        deep_max_prompt_chars=100_000,
        scan_max_prompt_chars=100_000,
        scan_max_files_per_batch=12,
        max_comment_entries=5,
        deep_timeout_base_seconds=300,
        deep_timeout_per_file_seconds=120,
        deep_timeout_max_seconds=1500,
    )

    package = build_review_context_package(
        plan, diff, manifest, checklist, comment_context=[], budget=budget,
        attention_plan=attention_plan,
    )

    assert len(package.batches) == 1
    assert list(package.batches[0].files_context.keys()) == ["core.py"]
    # The others are still described to the model, by tier, as files it is NOT reading.
    shape = "\n".join(package.batches[0].change_shape)
    assert "core.py | role=business_logic | reviewed here" in shape
    assert "ui.py | role=entrypoints_or_ui | glance" in shape
    assert "notes.md | role=docs_or_generated | skip" in shape


# ---------------------------------------------------------------------------
# Project context documents: paths the session reads itself
# ---------------------------------------------------------------------------


def test_context_docs_offer_only_files_that_exist_in_the_working_tree(tmp_path):
    """The defaults name conventional files, so they must be safe on a repo that has
    none of them: a pattern without a file is dropped silently."""
    from titan_plugin_github.operations.context_resolution_operations import (
        resolve_context_docs,
    )

    (tmp_path / "CLAUDE.md").write_text("rules\n")
    (tmp_path / "harness").mkdir()
    (tmp_path / "harness" / "README.md").write_text("focus\n")

    resolved = resolve_context_docs(
        ["CLAUDE.md", "AGENTS.md", "harness/README.md", "docs/architecture.md"],
        str(tmp_path),
        limit=8,
    )

    assert resolved == ["CLAUDE.md", "harness/README.md"]


def test_context_docs_keep_declared_order_and_respect_the_limit(tmp_path):
    """Declared order is the project's priority, and the cap is a bound on reading time
    inside the one deep call."""
    from titan_plugin_github.operations.context_resolution_operations import (
        resolve_context_docs,
    )

    for name in ("a.md", "b.md", "c.md"):
        (tmp_path / name).write_text("x\n")

    assert resolve_context_docs(["c.md", "a.md", "b.md"], str(tmp_path), limit=2) == [
        "c.md",
        "a.md",
    ]


def test_context_docs_expand_globs_deterministically(tmp_path):
    """Two runs of the same review must offer the same reading in the same order."""
    from titan_plugin_github.operations.context_resolution_operations import (
        resolve_context_docs,
    )

    (tmp_path / "docs").mkdir()
    for name in ("z.md", "a.md"):
        (tmp_path / "docs" / name).write_text("x\n")

    assert resolve_context_docs(["docs/*.md"], str(tmp_path), limit=8) == [
        "docs/a.md",
        "docs/z.md",
    ]


def test_context_docs_cannot_escape_the_working_tree(tmp_path):
    """A pattern that climbs out of the tree is not this project's documentation,
    whoever wrote it."""
    from titan_plugin_github.operations.context_resolution_operations import (
        resolve_context_docs,
    )

    (tmp_path / "outside.md").write_text("secret\n")
    inner = tmp_path / "repo"
    inner.mkdir()

    assert resolve_context_docs(["../outside.md"], str(inner), limit=8) == []


def test_context_docs_are_withheld_when_files_may_not_be_read(tmp_path):
    """Pointing the model at a file on disk is the same wrong-revision read as pasting
    it, so an unverified checkout offers nothing."""
    from titan_plugin_github.operations.context_resolution_operations import (
        resolve_context_docs,
    )

    (tmp_path / "CLAUDE.md").write_text("rules\n")

    assert (
        resolve_context_docs(["CLAUDE.md"], str(tmp_path), limit=8, allow_file_reads=False)
        == []
    )


def test_every_deep_file_shares_one_session_however_many_there_are():
    """The session is the unit of understanding (D-014).

    `DEEP_FILES_PER_SESSION = 12` used to chunk this: ragnarok PR 3685's 24 deep files
    became two sessions although they amount to ~53k chars against a 120,000 ceiling,
    paying twice for the manifest, context docs, checklist and comment context to obtain
    two sessions that could not talk — while the best findings this domain has produced
    were cross-file ones."""
    from titan_plugin_github.models.review_enums import AttentionTier
    from titan_plugin_github.operations.attention_operations import AttentionPlan, FileAttention

    paths = [f"f{i}.py" for i in range(5)]
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
    attention_plan = AttentionPlan(
        files=[FileAttention(path, AttentionTier.DEEP, "business_logic", "role") for path in paths]
    )
    budget = ReviewBudget(
        deep_files_per_session=2,
        deep_max_prompt_chars=100_000,
        scan_max_prompt_chars=100_000,
        scan_max_files_per_batch=12,
        max_comment_entries=5,
        deep_timeout_base_seconds=300,
        deep_timeout_per_file_seconds=120,
        deep_timeout_max_seconds=1500,
    )

    package = build_review_context_package(
        plan, diff, manifest, checklist, comment_context=[], budget=budget,
        attention_plan=attention_plan,
    )

    assert [batch.batch_id for batch in package.batches] == ["deep_1"]
    assert set(package.batches[0].files_context) == set(paths)


def test_the_least_important_file_gives_up_its_diff_first():
    """Degradation follows the ranking, not file size.

    An earlier version lowered one allowance for everyone, so whichever file happened to
    be large lost its diff — a big central file degraded before a small trivial one.
    `focus_files` arrives in the scorer's order, so the tail gives up its inline diff
    first and the core keeps it until last."""
    from titan_plugin_github.models.review_enums import AttentionTier
    from titan_plugin_github.operations.attention_operations import AttentionPlan, FileAttention

    # Same size on purpose: only the ranking can decide who degrades.
    paths = ["core.py", "middle.py", "trivial.py"]
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
    attention_plan = AttentionPlan(
        files=[FileAttention(path, AttentionTier.DEEP, "business_logic", "role") for path in paths]
    )
    budget = ReviewBudget(
        deep_files_per_session=12,
        # Room for roughly one file's diff plus the prompt skeleton.
        deep_max_prompt_chars=9_000,
        scan_max_prompt_chars=9_000,
        scan_max_files_per_batch=12,
        max_comment_entries=5,
        deep_timeout_base_seconds=300,
        deep_timeout_per_file_seconds=120,
        deep_timeout_max_seconds=1500,
    )

    package = build_review_context_package(
        plan, diff, manifest, checklist, comment_context=[], budget=budget,
        cwd=None, attention_plan=attention_plan,
    )

    context = package.batches[0].files_context
    assert set(context) == set(paths)  # everyone stays in the session
    assert context["trivial.py"].hunks == []  # the tail degraded
    assert context["core.py"].hunks  # the head kept its diff


def test_a_prompt_that_does_not_fit_loses_diff_detail_not_files():
    """Fidelity degrades; understanding does not divide.

    A file over its allowance keeps its reference and its hunk headers, and the session
    opens it from the working tree — so a tight ceiling costs anchoring detail on some
    files, never the ability to see them together."""
    from titan_plugin_github.models.review_enums import AttentionTier
    from titan_plugin_github.operations.attention_operations import AttentionPlan, FileAttention

    paths = [f"f{i}.py" for i in range(4)]
    diff = "".join(make_diff(path, "x" * 4000) for path in paths)
    plan = ReviewPlan(
        focus_files=[
            FileReviewPlan(path=path, priority=FileReviewPriority.HIGH, read_mode=FileReadMode.EXPANDED_HUNKS)
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
    attention_plan = AttentionPlan(
        files=[FileAttention(path, AttentionTier.DEEP, "business_logic", "role") for path in paths]
    )
    budget = ReviewBudget(
        deep_files_per_session=12,
        deep_max_prompt_chars=8_000,
        scan_max_prompt_chars=8_000,
        scan_max_files_per_batch=12,
        max_comment_entries=5,
        deep_timeout_base_seconds=300,
        deep_timeout_per_file_seconds=120,
        deep_timeout_max_seconds=1500,
    )

    package = build_review_context_package(
        plan, diff, manifest, checklist, comment_context=[], budget=budget,
        cwd=None, attention_plan=attention_plan,
    )

    assert len(package.batches) == 1
    batch = package.batches[0]
    assert set(batch.files_context) == set(paths)  # nobody is dropped
    # ...and the cost was paid in diff detail.
    assert any(not entry.hunks for entry in batch.files_context.values())


def test_flagged_files_join_the_same_session_as_a_second_task():
    """A question like "no test covers this path" is answered far better by whoever just
    read that path's code than by a separate call holding only the path (D-014)."""
    from titan_plugin_github.models.review_enums import AttentionTier
    from titan_plugin_github.operations.attention_operations import AttentionPlan, FileAttention

    diff = make_diff("core.py", "x" * 10) + make_diff("core_test.py", "y" * 10)
    plan = ReviewPlan(
        focus_files=[
            FileReviewPlan(path="core.py", priority=FileReviewPriority.HIGH, read_mode=FileReadMode.HUNKS_ONLY)
        ],
        review_axes=[ChecklistCategory.FUNCTIONAL_CORRECTNESS],
    )
    manifest = make_manifest(["core.py", "core_test.py"])
    checklist = [
        ReviewChecklistItem(
            id=ChecklistCategory.FUNCTIONAL_CORRECTNESS,
            name="Functional correctness",
            description="Does it work",
        )
    ]
    attention_plan = AttentionPlan(
        files=[
            FileAttention("core.py", AttentionTier.DEEP, "business_logic", "role"),
            FileAttention("core_test.py", AttentionTier.GLANCE, "tests", "role"),
        ]
    )

    package = build_review_context_package(
        plan, diff, manifest, checklist, comment_context=[], budget=review_budget_for_tests(),
        attention_plan=attention_plan,
        scan_suspicions=[{"path": "core_test.py", "note": "n", "suspicion": "is the path tested?"}],
    )

    batch = package.batches[0]
    assert set(batch.files_context) == {"core.py", "core_test.py"}
    # The flagged file carries headers and the question, never its diff.
    flagged = batch.files_context["core_test.py"]
    assert flagged.worktree_reference is True
    assert flagged.hunks == []
    assert flagged.changed_hunk_headers
    assert batch.scan_suspicions[0]["suspicion"] == "is the path tested?"


def review_budget_for_tests():
    from titan_plugin_github.operations.review_strategy_operations import review_budget

    return review_budget()


