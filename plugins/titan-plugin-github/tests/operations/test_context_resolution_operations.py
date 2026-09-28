"""The deep session built over the review material: which files it gets, in what order,
and what the checklist tells it about the rest."""

from titan_plugin_github.models.review_enums import AttentionTier, ChecklistCategory, FileChangeStatus
from titan_plugin_github.models.review_models import (
    ChangeManifest,
    ChangedFileEntry,
    FileReviewPlan,
    PullRequestManifest,
    ReviewChecklistItem,
    ReviewPlan,
)
from titan_plugin_github.operations.attention_operations import AttentionPlan, FileAttention
from titan_plugin_github.operations.context_resolution_operations import (
    build_review_context_package,
    resolve_context_docs,
)

CHECKLIST = [
    ReviewChecklistItem(id=ChecklistCategory.FUNCTIONAL_CORRECTNESS, name="Functional", description="d")
]


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


def make_plan(paths: list[str]) -> ReviewPlan:
    return ReviewPlan(
        focus_files=[FileReviewPlan(path=path) for path in paths],
        review_axes=[ChecklistCategory.FUNCTIONAL_CORRECTNESS],
    )


def test_glance_files_join_the_session_and_skipped_files_stay_out():
    """No triage call: the session covers the glance files itself, so they are its tasks,
    marked YOU, and a skipped file is only a checklist row."""
    paths = ["src/a.py", "tests/test_a.py", "conf.yml", "yarn.lock"]
    attention_plan = AttentionPlan(
        files=[
            FileAttention("src/a.py", AttentionTier.DEEP, "business_logic", "role"),
            FileAttention("tests/test_a.py", AttentionTier.GLANCE, "tests", "role"),
            FileAttention("conf.yml", AttentionTier.GLANCE, "config", "role"),
            FileAttention("yarn.lock", AttentionTier.SKIP, "config", "lockfile"),
        ]
    )

    package = build_review_context_package(
        make_plan(["src/a.py"]),
        make_manifest(paths),
        CHECKLIST,
        review_material={"src/a.py": True, "tests/test_a.py": True, "conf.yml": False, "yarn.lock": True},
        attention_plan=attention_plan,
    )

    assert len(package.batches) == 1
    batch = package.batches[0]
    assert list(batch.files_context) == ["src/a.py", "tests/test_a.py", "conf.yml"]
    assert "diff: `.titan-review/diffs/src/a.py.diff`" in batch.files_context["src/a.py"].review_hint
    assert "new file (no base version)" in batch.files_context["conf.yml"].review_hint
    shape = "\n".join(batch.change_shape)
    assert "conf.yml | role=config | YOU: review" in shape
    assert "yarn.lock | role=config | skip" in shape


def test_a_planned_file_outside_the_deep_tier_is_not_reviewed_in_depth():
    """On PR 251 a file the attention plan had tiered skip still went into the review
    when `focus_files` came straight from a scorer, which made the tiers decoration."""
    paths = ["core.py", "notes.md"]
    attention_plan = AttentionPlan(
        files=[
            FileAttention("core.py", AttentionTier.DEEP, "business_logic", "role"),
            FileAttention("notes.md", AttentionTier.SKIP, "docs_or_generated", "role"),
        ]
    )

    package = build_review_context_package(
        make_plan(paths),
        make_manifest(paths),
        CHECKLIST,
        review_material={"core.py": True, "notes.md": True},
        attention_plan=attention_plan,
    )

    assert list(package.batches[0].files_context) == ["core.py"]


def test_files_are_read_in_relation_order_with_each_test_after_its_subject():
    deep = ["src/a.py", "src/other/b.py", "tests/test_a.py"]
    attention_plan = AttentionPlan(
        files=[FileAttention(path, AttentionTier.DEEP, "business_logic", "role") for path in deep]
    )

    package = build_review_context_package(
        make_plan(deep),
        make_manifest(deep),
        CHECKLIST,
        review_material={path: True for path in deep},
        attention_plan=attention_plan,
    )

    assert list(package.batches[0].files_context) == ["src/a.py", "tests/test_a.py", "src/other/b.py"]


# ---------------------------------------------------------------------------
# Project context documents: paths the session reads itself
# ---------------------------------------------------------------------------


def test_context_docs_offer_only_files_that_exist_in_the_working_tree(tmp_path):
    """The defaults name conventional files, so they must be safe on a repo that has
    none of them: a pattern without a file is dropped silently."""
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
    for name in ("a.md", "b.md", "c.md"):
        (tmp_path / name).write_text("x\n")

    assert resolve_context_docs(["c.md", "a.md", "b.md"], str(tmp_path), limit=2) == [
        "c.md",
        "a.md",
    ]


def test_context_docs_expand_globs_deterministically(tmp_path):
    """Two runs of the same review must offer the same reading in the same order."""
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
    (tmp_path / "outside.md").write_text("secret\n")
    inner = tmp_path / "repo"
    inner.mkdir()

    assert resolve_context_docs(["../outside.md"], str(inner), limit=8) == []
