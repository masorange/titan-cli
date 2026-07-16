from titan_plugin_github.models.review_enums import ChecklistCategory, CommentContextKind
from titan_plugin_github.models.review_models import (
    CommentContextEntry,
    FileContextEntry,
    FocusContextBatch,
    PullRequestManifest,
    ReviewChecklistItem,
)
from titan_cli.core.result import ClientError, ClientSuccess
from titan_plugin_github.operations.findings_operations import (
    _annotate_diff_hunk,
    build_findings_prompt_parts,
    findings_json_schema,
    parse_findings_response,
    summarize_findings_prompt_parts,
)


def test_build_findings_prompt_parts_compacts_axes_and_pr_context():
    batch = FocusContextBatch(
        batch_id="batch_1",
        files_context={"src/foo.py": FileContextEntry(path="src/foo.py", hunks=["@@ -1 +1 @@\n+print('x')"])},
        comment_context=[
            CommentContextEntry(
                kind=CommentContextKind.COMMENT,
                thread_id="t1",
                path="src/foo.py",
                line=1,
                title="Existing",
                summary="Already mentioned",
                is_resolved=False,
            )
        ],
        checklist_applicable=[
            ReviewChecklistItem(
                id=ChecklistCategory.FUNCTIONAL_CORRECTNESS,
                name="Functional",
                description="Long description that should not appear in findings prompt axes",
            ),
            ReviewChecklistItem(
                id=ChecklistCategory.ERROR_HANDLING,
                name="Errors",
                description="Another long description",
            ),
        ],
        pr_manifest=PullRequestManifest(
            number=123,
            title="A very long pull request title that should be shortened in the findings prompt context if needed",
            base="main",
            head="feature/foo",
            author="alex",
            description="desc",
        ),
    )

    parts = build_findings_prompt_parts(batch)

    assert '"functional_correctness"' in parts["review_axes"]
    assert "Long description" not in parts["review_axes"]
    assert "Base" not in parts["pr_context"]
    assert "Batch: batch_1" in parts["pr_context"]
    assert "observable meaning of data, events, labels, classifications, or results" in parts["instructions"]
    assert "Do not report code style preferences" in parts["instructions"]


def test_summarize_findings_prompt_parts_returns_char_breakdown():
    parts = {
        "pr_context": "abc",
        "comments": "de",
        "review_axes": "fghi",
        "files_context": "j",
        "related_context": "",
        "instructions": "klmno",
        "schema": "pq",
        "prompt": "ignored",
    }

    summary = summarize_findings_prompt_parts(parts)

    assert summary == {
        "pr_context_chars": 3,
        "comment_context_chars": 2,
        "review_axes_chars": 4,
        "files_context_chars": 1,
        "related_context_chars": 0,
        "instructions_chars": 5,
        "schema_chars": 2,
    }


def test_build_findings_prompt_parts_renders_worktree_reference():
    batch = FocusContextBatch(
        batch_id="batch_2",
        files_context={
            "src/big.py": FileContextEntry(
                path="src/big.py",
                worktree_reference=True,
                review_hint="Read this file from the worktree and inspect the changed regions first.",
                changed_hunk_headers=["@@ -10,20 +10,30 @@", "@@ -80,5 +90,12 @@"],
            )
        },
        checklist_applicable=[
            ReviewChecklistItem(
                id=ChecklistCategory.FUNCTIONAL_CORRECTNESS,
                name="Functional",
                description="desc",
            )
        ],
    )

    parts = build_findings_prompt_parts(batch)

    assert "Read from worktree instead of inline context." in parts["files_context"]
    assert "Changed regions to inspect first:" in parts["files_context"]
    assert "@@ -10,20 +10,30 @@" in parts["files_context"]


# ---------------------------------------------------------------------------
# _annotate_diff_hunk()
# ---------------------------------------------------------------------------


def test_annotate_diff_hunk_numbers_added_and_context_lines():
    hunk = "@@ -10,2 +10,3 @@\n def bar():\n+    return 1\n-    return 0"

    result = _annotate_diff_hunk(hunk)

    assert "10 [CONTEXT] def bar():" in result
    assert "11 [ADDED]     return 1" in result
    assert "[DELETED - do not review]     return 0" in result


def test_annotate_diff_hunk_does_not_number_surrounding_context_lines():
    """Regression test: `expanded_hunks` entries prepend a raw, non-diff-prefixed
    surrounding-context block before the real diff hunk (DiffContextManager.build_expanded_hunks).
    Indented raw lines in that block must not be mislabeled as numbered [CONTEXT] diff lines."""
    hunk = (
        "@@ -10,2 +10,3 @@\n"
        "# --- surrounding context (lines 8-12) ---\n"
        "    def foo():\n"
        "        pass\n"
        "def bar():\n"
        "# --- diff hunk ---\n"
        " def bar():\n"
        "+    return 1\n"
        "-    return 0"
    )

    result = _annotate_diff_hunk(hunk)

    assert "    def foo():" in result
    assert "[CONTEXT]    def foo():" not in result
    assert "        pass" in result
    assert "[CONTEXT]        pass" not in result


def test_annotate_diff_hunk_real_hunk_numbering_unaffected_by_surrounding_context():
    """The actual diff-hunk lines after the '# --- diff hunk ---' marker must get the same
    line numbers they would get without the surrounding-context preamble at all — the raw
    preamble lines must not advance the line counter."""
    plain_hunk = "@@ -10,2 +10,3 @@\n def bar():\n+    return 1\n-    return 0"
    expanded_hunk = (
        "@@ -10,2 +10,3 @@\n"
        "# --- surrounding context (lines 8-12) ---\n"
        "    def foo():\n"
        "        pass\n"
        "def bar():\n"
        "# --- diff hunk ---\n"
        " def bar():\n"
        "+    return 1\n"
        "-    return 0"
    )

    plain_result = _annotate_diff_hunk(plain_hunk)
    expanded_result = _annotate_diff_hunk(expanded_hunk)

    plain_diff_lines = plain_result.splitlines()[1:]  # drop the @@ header
    expanded_diff_lines = expanded_result.splitlines()[-len(plain_diff_lines):]
    assert expanded_diff_lines == plain_diff_lines


# ---------------------------------------------------------------------------
# findings_json_schema() / parse_findings_response()
# ---------------------------------------------------------------------------


def test_findings_json_schema_wraps_array_in_object_with_findings_key():
    schema = findings_json_schema()

    assert schema["type"] == "object"
    assert schema["required"] == ["findings"]
    assert schema["properties"]["findings"]["type"] == "array"


def test_parse_findings_response_unstructured_parses_bare_array():
    result = parse_findings_response('[{"title": "Bug"}]', structured=False)

    assert isinstance(result, ClientSuccess)
    assert result.data == [{"title": "Bug"}]


def test_parse_findings_response_structured_unwraps_findings_key():
    result = parse_findings_response('{"findings": [{"title": "Bug"}]}', structured=True)

    assert isinstance(result, ClientSuccess)
    assert result.data == [{"title": "Bug"}]


def test_parse_findings_response_structured_errors_when_findings_key_missing():
    result = parse_findings_response('{"other": []}', structured=True)

    assert isinstance(result, ClientError)
    assert result.error_code == "MISSING_FINDINGS_FIELD"


def test_parse_findings_response_structured_falls_back_to_error_on_prose():
    result = parse_findings_response("I refuse to call that tool.", structured=True)

    assert isinstance(result, ClientError)
