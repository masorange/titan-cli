from titan_cli.core.result import ClientError, ClientSuccess
from titan_plugin_github.models.review_models import Finding
from titan_plugin_github.operations.findings_operations import (
    REVIEW_ALLOWED_TOOLS,
    REVIEW_DISALLOWED_TOOLS,
    build_free_review_prompt,
    free_review_json_schema,
    normalize_finding_path,
    parse_findings_response,
    partition_findings_by_path,
    to_finding_payload,
)


def _prompt() -> str:
    return build_free_review_prompt(273, "Add Firebase plugin", "feat/firebase", "master", "/repo/.titan/worktrees/titan-review-273")


def test_prompt_names_the_pr_and_points_at_the_material():
    prompt = _prompt()

    assert '#273 "Add Firebase plugin" (feat/firebase → master)' in prompt
    for path in (".titan-review/pr.md", ".titan-review/pr.diff", ".titan-review/diffs/", ".titan-review/base/"):
        assert path in prompt


def test_prompt_names_the_worktree_by_its_absolute_path():
    prompt = _prompt()

    assert "`/repo/.titan/worktrees/titan-review-273` is a checkout of the PR head" in prompt
    assert "Work only inside it" in prompt


def test_subagents_are_only_suggested_to_a_cli_that_can_spawn_them():
    args = (273, "Add Firebase plugin", "feat/firebase", "master", "/repo/wt")

    assert "subagents" not in build_free_review_prompt(*args)
    assert "subagents" not in build_free_review_prompt(*args, use_subagents=False)
    assert "split the work across subagents" in build_free_review_prompt(*args, use_subagents=True)


def test_subagents_are_told_to_run_in_the_foreground_and_be_awaited():
    """A headless session that ends its turn to wait for a background subagent loses it."""
    prompt = build_free_review_prompt(273, "t", "h", "b", "/repo/wt", use_subagents=True)

    assert "in the foreground" in prompt
    assert "answer only once every one has reported" in prompt


def test_prompt_asks_for_a_review_and_prescribes_no_procedure():
    prompt = _prompt()

    assert "Review it as a senior engineer would" in prompt
    # The procedure the directed session carried, and that turned the review into a form.
    for word in ("focus", "ledger", "reviewed", "key_facts", "open_suspicions", "checklist"):
        assert word not in prompt


def test_prompt_forbids_running_tests_because_ci_does():
    assert "Do not run tests or builds: CI runs them." in _prompt()


def test_prompt_asks_not_to_repeat_existing_comments():
    assert "Do not raise again what a comment already raises." in _prompt()


def test_prompt_shows_the_answer_shape_for_clis_without_a_schema():
    prompt = _prompt()

    for field in ('"path"', '"line"', '"severity"', '"title"', '"body"', '"snippet"'):
        assert field in prompt


def test_schema_is_the_findings_list_only():
    schema = free_review_json_schema()

    assert schema["type"] == "object"
    assert schema["required"] == ["findings"]
    item = schema["properties"]["findings"]["items"]
    assert set(item["properties"]) == {"path", "line", "severity", "title", "body", "snippet"}
    assert item["properties"]["severity"]["enum"] == ["blocking", "important", "nit"]


def test_session_may_use_subagents_and_read_only_git_but_not_edit():
    assert "Agent" not in REVIEW_DISALLOWED_TOOLS
    assert "Bash" not in REVIEW_DISALLOWED_TOOLS
    assert {"Edit", "Write", "NotebookEdit", "WebFetch", "WebSearch"} <= set(REVIEW_DISALLOWED_TOOLS)
    # A `--print` session has no later turn to wake.
    assert "ScheduleWakeup" in REVIEW_DISALLOWED_TOOLS
    assert all(rule.startswith("Bash(git ") for rule in REVIEW_ALLOWED_TOOLS)


def test_parse_findings_response_unstructured_parses_bare_array():
    result = parse_findings_response('[{"title": "Bug"}]', structured=False)

    assert isinstance(result, ClientSuccess)
    assert result.data == [{"title": "Bug"}]


def test_parse_findings_response_unstructured_takes_the_envelope_from_prose():
    stdout = 'Done.\n```json\n{"findings": [{"title": "Bug"}]}\n```'

    result = parse_findings_response(stdout, structured=False)

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


def test_a_session_finding_maps_onto_a_valid_finding():
    payload = to_finding_payload(
        {
            "path": "a.py",
            "line": 12,
            "severity": "important",
            "title": "Crash on empty default",
            "body": "`raw` is never None here, so the default branch is dead.",
            "snippet": "if raw is not None:",
        }
    )

    finding = Finding.model_validate(payload)
    assert finding.why == finding.suggested_comment == "`raw` is never None here, so the default branch is dead."
    assert finding.evidence == finding.snippet == "if raw is not None:"
    assert finding.category == "review"
    assert finding.line == 12


def test_a_finding_without_line_or_snippet_still_validates():
    payload = to_finding_payload({"path": "a.py", "line": "n/a", "severity": "nit", "title": "t", "body": "b"})

    finding = Finding.model_validate(payload)
    assert finding.line is None
    assert finding.snippet is None
    assert finding.evidence == ""


def test_a_quoted_line_number_is_kept_and_a_boolean_is_not():
    quoted = to_finding_payload({"path": "a.py", "line": " 42 ", "severity": "nit", "title": "t", "body": "b"})
    boolean = to_finding_payload({"path": "a.py", "line": True, "severity": "nit", "title": "t", "body": "b"})

    assert quoted["line"] == 42
    assert boolean["line"] is None


def test_a_non_dict_finding_is_left_for_normalization_to_reject():
    assert to_finding_payload("oops") == "oops"


def test_partition_keeps_pr_files_in_the_prs_spelling():
    kept, rejected = partition_findings_by_path([{"path": "./src\\a.py", "title": "t"}], {"src/a.py"})

    assert kept == [{"path": "src/a.py", "title": "t"}]
    assert rejected == []


def test_partition_keeps_real_files_outside_the_pr_and_drops_invented_ones():
    findings = [{"path": "router.kt", "title": "regression"}, {"path": "ghost.kt", "title": "made up"}]

    kept, rejected = partition_findings_by_path(findings, {"a.kt"}, lambda path: path == "router.kt")

    assert kept == [{"path": "router.kt", "title": "regression"}]
    assert rejected == [{"path": "ghost.kt", "title": "made up"}]


def test_partition_moves_findings_on_review_material_to_the_file_it_copies():
    findings = [
        {"path": ".titan-review/base/src/a.py", "title": "old code"},
        {"path": ".titan-review/diffs/src/a.py.diff", "title": "diff"},
        {"path": ".titan-review/pr.md", "title": "about the PR file"},
    ]

    kept, rejected = partition_findings_by_path(findings, {"src/a.py"}, lambda path: True)

    assert kept == [{"path": "src/a.py", "title": "old code"}, {"path": "src/a.py", "title": "diff"}]
    assert rejected == [{"path": ".titan-review/pr.md", "title": "about the PR file"}]


def test_partition_drops_the_line_of_a_finding_moved_off_review_material():
    findings = [
        {"path": ".titan-review/diffs/src/a.py.diff", "line": 40, "snippet": "x = 1", "title": "diff"},
        {"path": "src/a.py", "line": 12, "title": "direct"},
    ]

    kept, _ = partition_findings_by_path(findings, {"src/a.py"}, lambda path: True)

    assert kept == [
        {"path": "src/a.py", "line": None, "snippet": "x = 1", "title": "diff"},
        {"path": "src/a.py", "line": 12, "title": "direct"},
    ]


def test_partition_keeps_pathless_findings():
    kept, rejected = partition_findings_by_path([{"title": "general"}], {"a.py"})

    assert kept == [{"title": "general"}]
    assert rejected == []


def test_normalize_finding_path_only_strips_separators_and_dot_prefix():
    assert normalize_finding_path(" ././Src\\A.py ") == "Src/A.py"
