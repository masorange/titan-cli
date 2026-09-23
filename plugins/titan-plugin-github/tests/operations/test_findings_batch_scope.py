"""Tests for the batch-scope guard on findings.

The invariant: a findings batch may only report on files it actually showed the model.
It matters because the anchoring layer can resolve a line in ANY file of the PR, so a
finding whose path the batch never sent still anchors and publishes — on a file nobody
looked at. With one or two files per batch that is unlikely; with ten or fifteen packed
into one prompt it is an ordinary mistake.

What this does NOT claim to catch: the model naming file A while meaning file B when
BOTH were in the batch. That is undetectable here by construction, and the defence for
it lives in the anchor resolver, which only accepts a snippet match inside the file the
finding names.
"""

from titan_plugin_github.models.review_models import FileContextEntry, FocusContextBatch
from titan_plugin_github.operations.findings_operations import (
    batch_scope_paths,
    normalize_finding_path,
    partition_findings_by_batch_scope,
)


def _batch(paths: list[str], related: dict[str, str] | None = None) -> FocusContextBatch:
    return FocusContextBatch(
        batch_id="batch_1",
        files_context={path: FileContextEntry(path=path) for path in paths},
        related_files=related or {},
    )


def _finding(path: str, title: str = "Bug") -> dict:
    return {"path": path, "title": title, "severity": "important", "why": "because"}


class TestScopePaths:

    def test_scope_is_the_batchs_own_files(self):
        batch = _batch(["a/one.py", "b/two.py"])

        assert batch_scope_paths(batch) == {"a/one.py", "b/two.py"}

    def test_related_context_contributes_the_path_it_was_requested_for(self):
        """Related keys are stored as "<request type>:<path>"; the path half is a real
        file of the PR and the model saw it named in the prompt."""
        batch = _batch(["a/one.py"], related={"related_context:a/one.py": "...",
                                              "related_tests:b/two.py": "..."})

        assert batch_scope_paths(batch) == {"a/one.py", "b/two.py"}

    def test_the_unlabelled_sibling_behind_related_content_is_not_in_scope(self):
        """The content comes from a sibling (__init__.py, protocols.py, base_*) whose
        own path is recorded nowhere, so a finding naming it is the model inferring a
        path rather than reading one."""
        batch = _batch(["a/one.py"], related={"related_context:a/one.py": "..."})

        assert "a/__init__.py" not in batch_scope_paths(batch)


class TestNormalization:

    def test_windows_separators_and_dot_slash_are_canonicalised(self):
        assert normalize_finding_path("a\\b\\c.py") == "a/b/c.py"
        assert normalize_finding_path("./a/one.py") == "a/one.py"
        assert normalize_finding_path(".././a/one.py") == ".././a/one.py"

    def test_case_is_preserved(self):
        """Paths are case-sensitive where this runs; folding would let two real files
        collide."""
        assert normalize_finding_path("A/One.py") == "A/One.py"

    def test_empty_and_none_are_safe(self):
        assert normalize_finding_path("") == ""
        assert normalize_finding_path(None) == ""


class TestPartition:

    def test_findings_about_the_batchs_files_are_kept(self):
        kept, rejected = partition_findings_by_batch_scope(
            [_finding("a/one.py"), _finding("b/two.py")],
            {"a/one.py", "b/two.py"},
            {"a/one.py", "b/two.py", "c/three.py"},
        )

        assert len(kept) == 2
        assert rejected == []

    def test_a_real_pr_file_outside_this_batch_is_dropped_as_outside_batch(self):
        """The dangerous case: it CAN anchor, because the diff manager holds the whole
        PR, so it would publish on a file the model never read."""
        kept, rejected = partition_findings_by_batch_scope(
            [_finding("c/three.py", title="Wrong file")],
            {"a/one.py"},
            {"a/one.py", "c/three.py"},
        )

        assert kept == []
        assert rejected == [{"path": "c/three.py", "reason": "outside_batch", "title": "Wrong file"}]

    def test_a_path_absent_from_the_pr_is_dropped_as_unknown(self):
        kept, rejected = partition_findings_by_batch_scope(
            [_finding("does/not/exist.py")], {"a/one.py"}, {"a/one.py"}
        )

        assert kept == []
        assert rejected[0]["reason"] == "unknown_path"

    def test_the_two_reasons_are_reported_separately(self):
        """They mean different things — one is a hallucination, the other a real file
        shown to a different batch — and the rates diverge."""
        _, rejected = partition_findings_by_batch_scope(
            [_finding("c/three.py"), _finding("nope.py")],
            {"a/one.py"},
            {"a/one.py", "c/three.py"},
        )

        assert [r["reason"] for r in rejected] == ["outside_batch", "unknown_path"]

    def test_a_formatting_difference_is_accepted_and_rewritten(self):
        """A correct finding must never be lost to a "./" prefix, and downstream code
        compares paths by string, so it is rewritten to the batch's own spelling."""
        kept, rejected = partition_findings_by_batch_scope(
            [_finding("./a/one.py")], {"a/one.py"}, {"a/one.py"}
        )

        assert rejected == []
        assert kept[0]["path"] == "a/one.py"

    def test_rewriting_does_not_mutate_the_original_finding(self):
        original = _finding("./a/one.py")
        kept, _ = partition_findings_by_batch_scope([original], {"a/one.py"}, {"a/one.py"})

        assert original["path"] == "./a/one.py"
        assert kept[0] is not original

    def test_an_already_canonical_finding_is_passed_through_untouched(self):
        original = _finding("a/one.py")
        kept, _ = partition_findings_by_batch_scope([original], {"a/one.py"}, {"a/one.py"})

        assert kept[0] is original

    def test_a_pathless_finding_is_kept(self):
        """A general observation is not misattributed to anything, and the publish layer
        already handles a finding with no path."""
        kept, rejected = partition_findings_by_batch_scope(
            [{"title": "The PR has no tests", "severity": "nit"}], {"a/one.py"}, {"a/one.py"}
        )

        assert len(kept) == 1
        assert rejected == []

    def test_a_blank_path_counts_as_pathless_rather_than_unknown(self):
        kept, rejected = partition_findings_by_batch_scope(
            [_finding("   ")], {"a/one.py"}, {"a/one.py"}
        )

        assert len(kept) == 1
        assert rejected == []

    def test_no_findings_is_not_an_error(self):
        assert partition_findings_by_batch_scope([], {"a/one.py"}, {"a/one.py"}) == ([], [])

    def test_without_a_manifest_everything_unknown_drops_the_same_way(self):
        """An empty manifest makes every unfamiliar path read as hallucinated, which is
        the safe direction: both reasons drop the finding."""
        kept, rejected = partition_findings_by_batch_scope(
            [_finding("c/three.py")], {"a/one.py"}, set()
        )

        assert kept == []
        assert rejected[0]["reason"] == "unknown_path"

    def test_rejections_carry_only_what_a_log_line_needs(self):
        """Not the whole finding: telemetry should not grow a copy of the review."""
        _, rejected = partition_findings_by_batch_scope(
            [_finding("nope.py", title="Something")], {"a/one.py"}, {"a/one.py"}
        )

        assert set(rejected[0]) == {"path", "reason", "title"}


def test_a_skim_suspicion_puts_its_file_in_scope():
    """Without this the first pass is thrown away.

    The skim's suspicions name files that are NOT in the deep batch's files_context — the
    session is told to open them in the working tree and settle the question. The scope
    check (cov-002) would otherwise drop every finding that work leads to, silently, as a
    path the batch was never shown."""
    from titan_plugin_github.models.review_models import FocusContextBatch
    from titan_plugin_github.operations.findings_operations import batch_scope_paths

    batch = FocusContextBatch(
        batch_id="deep_1",
        scan_suspicions=[
            {"path": "tests/core/security/test_vault.py", "note": "n", "suspicion": "s"},
            {"path": "", "note": "n", "suspicion": "s"},
        ],
    )

    assert batch_scope_paths(batch) == {"tests/core/security/test_vault.py"}
