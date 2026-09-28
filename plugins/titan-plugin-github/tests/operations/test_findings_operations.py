from titan_plugin_github.models.review_enums import ChecklistCategory
from titan_plugin_github.models.review_models import (
    FileContextEntry,
    FocusContextBatch,
    PullRequestManifest,
    ReviewChecklistItem,
)
from titan_cli.core.result import ClientError, ClientSuccess
from titan_plugin_github.operations.findings_operations import (
    build_findings_prompt_parts,
    findings_json_schema,
    parse_findings_response,
    summarize_findings_prompt_parts,
)


def test_build_findings_prompt_parts_compacts_axes_and_pr_context():
    batch = FocusContextBatch(
        batch_id="batch_1",
        files_context={"src/foo.py": FileContextEntry(path="src/foo.py", review_hint="diff: `x`")},
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
    # review-quality-001 (D-002 approved): applicable checklist items now include
    # name + description (capped) so the findings model knows what each axis means.
    assert "Long description that should not appear" in parts["review_axes"]
    assert '"name": "Functional"' in parts["review_axes"]
    assert "Base" not in parts["pr_context"]
    assert "Batch: batch_1" in parts["pr_context"]
    assert "what data, events, labels or results MEAN" in parts["instructions"]
    assert "Not style, naming, refactor or architecture preferences" in parts["instructions"]


def test_summarize_findings_prompt_parts_returns_char_breakdown():
    parts = {
        "pr_context": "abc",
        "review_axes": "fghi",
        "files_context": "j",
        "instructions": "klmno",
        "schema": "pq",
        "prompt": "ignored",
    }

    summary = summarize_findings_prompt_parts(parts)

    assert summary == {
        "pr_context_chars": 3,
        "review_axes_chars": 4,
        "files_context_chars": 1,
        "instructions_chars": 5,
        "schema_chars": 2,
    }


# ---------------------------------------------------------------------------
# findings_json_schema() / parse_findings_response()
# ---------------------------------------------------------------------------


def test_findings_json_schema_wraps_array_in_object_with_findings_key():
    schema = findings_json_schema()

    assert schema["type"] == "object"
    # Both sides required: a findings-only schema teaches the model that "this is fine"
    # is not an answer, and then a file found clean looks exactly like one ignored.
    assert schema["required"] == ["findings", "focus", "reviewed", "key_facts", "open_suspicions"]
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


# ---------------------------------------------------------------------------
# review-quality-001/002: checklist content cap + PR intent (D-002 token mandate)
# ---------------------------------------------------------------------------

def test_checklist_descriptions_are_hard_capped():
    from titan_plugin_github.operations.findings_operations import _checklist_to_json

    items = [
        ReviewChecklistItem(
            id=ChecklistCategory.SECURITY,
            name="Security",
            description="x" * 500,
        )
    ]

    rendered = _checklist_to_json(items)

    assert "x" * 200 in rendered
    assert "x" * 201 not in rendered


def test_pr_context_carries_the_authors_description_as_its_own_section():
    batch = FocusContextBatch(
        batch_id="batch_1",
        files_context={"src/foo.py": FileContextEntry(path="src/foo.py")},
        checklist_applicable=[],
        pr_manifest=PullRequestManifest(
            number=3597,
            title="Marketplace token retry",
            base="develop",
            head="feat/marketplace-token-retry",
            author="alex",
            # Real-world shape (PR #3597): meme image first, then the actual intent.
            description=(
                "\n![Token Refresh Meme](https://media.giphy.com/media/abc/giphy.gif)\n\n"
                "### PR's key points\n"
                "This PR implements a robust token retry mechanism for Marketplace API calls "
                "to handle scenarios where the local token expiration check is out of sync."
            ),
        ),
    )

    parts = build_findings_prompt_parts(batch)

    # The whole cleaned description, in its own section, whatever template it uses: no
    # guessing which line matters, only generic markup (the meme image) removed.
    assert "## What the author says this PR does" in parts["pr_context"]
    assert "This PR implements a robust token retry mechanism" in parts["pr_context"]
    assert "giphy" not in parts["pr_context"]


def test_pr_context_omits_intent_when_description_is_only_noise():
    batch = FocusContextBatch(
        batch_id="batch_1",
        files_context={"src/foo.py": FileContextEntry(path="src/foo.py")},
        checklist_applicable=[],
        pr_manifest=PullRequestManifest(
            number=1,
            title="T",
            base="main",
            head="f",
            author="a",
            description="<!-- template -->\n![img](https://x.com/i.png)\n- [ ] checkbox\n",
        ),
    )

    parts = build_findings_prompt_parts(batch)

    assert "## What the author says this PR does" not in parts["pr_context"]


def test_extract_pr_intent_strips_noise_and_caps():
    from titan_plugin_github.operations.prompt_formatting_operations import extract_pr_intent

    description = (
        "<!-- PR template: fill everything -->\n"
        "![badge](https://img.shields.io/badge.svg)\n"
        "## Summary\n"
        "Adds retry logic to the token refresh flow.\n"
        "- [x] Tests added\n"
        "- [ ] Docs updated\n"
        "https://jira.example.com/TICKET-123\n"
        "More prose here.\n"
    )

    result = extract_pr_intent(description, max_chars=800)

    assert "Summary" in result
    assert "Adds retry logic" in result
    assert "More prose here." in result
    assert "badge" not in result
    assert "Tests added" not in result
    assert "jira.example.com" not in result
    assert "template" not in result


def test_the_review_gets_the_authors_whole_ask_not_the_template_heading():
    """Measured on ragnarok PR #3720: the review received ONE line, the template heading
    "PR's Trigger (Check the VALIDITY of these links)", and the author's own request to
    verify that deleted events were covered by the mapping never reached the model."""
    from titan_plugin_github.operations.prompt_formatting_operations import review_pr_description

    description = (
        "### PR's Trigger (Check the VALIDITY of these links) <!-- REMOVE WHAT DOESN'T APPLY -->\n"
        "* JIRA Issue: ECAPP-1667\n"
        '<img src="https://i.imgflip.com/b1u5bw.jpg" width="400"/>\n\n'
        "### PR's key points\n"
        "Part 2 of many. Check AnalyticsStore specially.\n"
        + "- a bullet about the migration\n" * 40
        + "### How to review this PR?\n"
        "Verify that the deletions are properly covered by the new entries in analytics_mapping.json.\n"
    )

    result = review_pr_description(description)

    assert "Check AnalyticsStore specially" in result
    assert "Verify that the deletions are properly covered" in result
    assert "<img" not in result and "REMOVE WHAT" not in result
    assert review_pr_description("") == ""


def test_default_titan_checklist_renders_with_descriptions_too():
    """The checklist content fix must work without a project override: Titan's
    built-in DEFAULT_REVIEW_CHECKLIST (served by ChecklistManager when no
    .titan/review/checklist.yaml exists) must reach the findings prompt with
    name + description, same as any project checklist."""
    from titan_plugin_github.checklists.defaults import DEFAULT_REVIEW_CHECKLIST
    from titan_plugin_github.operations.findings_operations import _checklist_to_json

    assert all(item.name and item.description for item in DEFAULT_REVIEW_CHECKLIST)

    rendered = _checklist_to_json(list(DEFAULT_REVIEW_CHECKLIST)[:4])

    assert '"name": "Functional Correctness"' in rendered
    assert "Logic bugs" in rendered


# ============================================================================
# The whole-change framing (cov-016)
# ============================================================================


def test_prompt_reviews_the_pr_when_it_carries_the_change_shape():
    """A batch that holds the whole change's shape IS the review, and is told so.

    The framing is the substance: "one bounded review batch" asks the model to report what
    it can see in the files it was handed, which is all a per-file batch could ever do.
    With the shape, it can judge the change against what the PR claims and say what is
    missing."""
    from titan_plugin_github.models.review_models import FocusContextBatch, PullRequestManifest
    from titan_plugin_github.operations.findings_operations import build_findings_prompt_parts

    batch = FocusContextBatch(
        batch_id="batch_1",
        change_shape=[
            "core.py | role=business_logic | YOU: review | +40/-3",
            "ui.py | role=entrypoints_or_ui | glance | +5/-1",
        ],
        pr_intent="Adds an OAuth manager so plugins stop each refreshing their own token.",
        pr_manifest=PullRequestManifest(
            number=251,
            title="Add shared OAuth manager",
            description="body",
            base="master",
            head="feat",
            author="someone",
        ),
    )

    parts = build_findings_prompt_parts(batch)

    assert "Review this pull request." in parts["prompt"]
    assert "one bounded review batch" not in parts["prompt"]
    assert "## Checklist (every changed file in this PR)" in parts["prompt"]
    assert "ui.py | role=entrypoints_or_ui | glance | +5/-1" in parts["prompt"]
    # The intent carried on the batch wins over the 200-char line pulled from the body.
    assert "stop each refreshing their own token" in parts["prompt"]
    # The session's own rows are named as its tasks; the rest are context.
    assert "Rows marked YOU are your tasks" in parts["prompt"]


def test_prompt_keeps_a_narrow_framing_without_a_change_shape():
    """A batch without the change's shape must not claim to be reviewing the whole PR nor
    be asked to judge the change as a whole."""
    from titan_plugin_github.models.review_models import FocusContextBatch
    from titan_plugin_github.operations.findings_operations import build_findings_prompt_parts

    parts = build_findings_prompt_parts(FocusContextBatch(batch_id="batch_2"))

    assert "They are part of a larger pull request" in parts["prompt"]
    assert "step back and judge the change" not in parts["task"]
    assert "## Checklist" not in parts["prompt"]
    assert parts["change_shape"] == ""


def test_cross_file_instructions_appear_only_when_the_batch_holds_several_files():
    """The deep session is asked for cross-file problems explicitly.

    A session that CAN see several files together does not necessarily go looking: on run
    4fd7f345 the separate synthesis call found mismatched credential labels and a
    duplicated redaction policy that `deep_1`, holding all seven files, had not reported.
    That call cost $0.8478 of the review's $1.9694 to ask three questions; the questions
    now travel in the prompt. A single-file batch (an overflow slice) must not be asked,
    since it has nothing to compare."""
    from titan_plugin_github.models.review_models import FileContextEntry, FocusContextBatch
    from titan_plugin_github.operations.findings_operations import build_findings_prompt_parts

    def entry(path: str) -> FileContextEntry:
        return FileContextEntry(path=path, review_hint="h")

    one_file = build_findings_prompt_parts(
        FocusContextBatch(batch_id="deep_1a", files_context={"a.py": entry("a.py")})
    )
    several = build_findings_prompt_parts(
        FocusContextBatch(
            batch_id="deep_1",
            files_context={"a.py": entry("a.py"), "b.py": entry("b.py")},
        )
    )

    assert "mismatches ACROSS them" not in one_file["instructions"]
    assert "mismatches ACROSS them" in several["instructions"]
    # The rest of the prompt is untouched in both.
    for parts in (one_file, several):
        assert "Report only what has an observable impact" in parts["instructions"]
        assert "return an empty `findings` list" in parts["task"]


def test_project_context_section_asks_for_lookup_not_for_reading_everything():
    """The documents are consulted, not read end to end.

    A repo's CLAUDE.md or architecture notes can run to thousands of lines, and the one
    deep call's time is the review's time. The section names what bears on the files
    under review and says to stop there; the instruction also requires the session to
    OPEN anything outside the diff before asserting what it does — the failure behind
    ragnarok run 8b7aef16's first finding, which claimed what every product flavor's
    manifest contains while holding only `src/main`'s."""
    from titan_plugin_github.models.review_models import FocusContextBatch
    from titan_plugin_github.operations.findings_operations import build_findings_prompt_parts

    with_docs = build_findings_prompt_parts(
        FocusContextBatch(batch_id="deep_1", context_docs=["CLAUDE.md"])
    )
    without = build_findings_prompt_parts(FocusContextBatch(batch_id="deep_1"))

    assert "do NOT read end to end" in with_docs["prompt"]
    assert "only what bears on the files below" in with_docs["prompt"]
    assert "open it in the working tree and check" in with_docs["instructions"]
    # Nothing about project context when none was resolved: an instruction to read a
    # list that is not there invites the model to go looking for one.
    assert "Project Context" not in without["prompt"]
    assert without["context_docs"] == ""


def test_the_findings_prompt_renders_every_axis_the_plan_selected():
    """The renderer had the SAME `[:4]` as select_review_axes, applied a second time, so
    even a plan that selected 8 axes could only ever ask about 4. Two independent
    truncations of one list."""
    from titan_plugin_github.models.review_enums import ChecklistCategory
    from titan_plugin_github.models.review_models import FocusContextBatch, ReviewChecklistItem
    from titan_plugin_github.operations.findings_operations import build_findings_prompt_parts

    checklist = [
        ReviewChecklistItem(id=category, name=str(category), description="d")
        for category in list(ChecklistCategory)[:8]
    ]

    parts = build_findings_prompt_parts(
        FocusContextBatch(batch_id="deep_1", checklist_applicable=checklist)
    )

    for item in checklist:
        assert str(item.id) in parts["review_axes"]


def test_the_session_is_told_to_search_before_claiming_an_absence():
    """The serious findings are absences, and an absence needs a search.

    On ragnarok PR #3692, a free-form Claude Code session found 19 findings to Titan's 6,
    and all three of its `blocking` items were absences: a function with zero callers, a
    hang traced to a fake, a config no flavor overrides. Titan's session HAS Grep and Glob
    — only `Bash` and the write/fetch tools are disallowed — so the gap was that nothing
    told it to look.

    Both rules also have to be unconditional: the verify-before-asserting rule used to
    hang off `context_docs`, so a repo with no CLAUDE.md never saw it."""
    from titan_plugin_github.models.review_models import FileContextEntry, FocusContextBatch
    from titan_plugin_github.operations.findings_operations import build_findings_prompt_parts

    bare = FocusContextBatch(batch_id="deep_1", files_context={"a.py": FileContextEntry(path="a.py")})

    instructions = build_findings_prompt_parts(bare)["instructions"]

    assert "SEARCH the working tree" in instructions
    assert "An absence claimed without a search is a guess" in instructions
    assert "open it in the working tree and check" in instructions
    # No project documents on this batch, so the rules may not be gated behind them.
    assert not bare.context_docs


def test_the_deep_review_is_asked_what_a_removal_breaks():
    """"Do not report deleted lines" made the session pass over the removal of reducers
    whose actions are still dispatched (ragnarok PR #3720). A deleted line is still not a
    finding by itself; what its removal breaks is, once the replacement was searched for."""
    parts = build_findings_prompt_parts(FocusContextBatch(batch_id="deep_1"))

    assert "Do not report deleted lines" not in parts["instructions"]
    assert "what its removal BREAKS" in parts["instructions"]
    assert "SEARCH for the replacement" in parts["instructions"]


def test_the_task_and_its_coverage_come_before_the_material():
    """On #236 (run 7d61a0b9) the session accounted for 32 of 58 deep files: covering
    every file was one instruction among ~20, after 339k chars of diffs. It is now the
    first task, stated before any material, and the two rules written for a session with
    no working tree -- which contradicted "open it and check" -- are gone."""
    from titan_plugin_github.models.review_models import FileContextEntry, FocusContextBatch
    from titan_plugin_github.operations.findings_operations import build_findings_prompt_parts

    parts = build_findings_prompt_parts(
        FocusContextBatch(
            batch_id="deep_1",
            change_shape=["a.py | role=business_logic | YOU: review | +1/-0"],
            files_context={"a.py": FileContextEntry(path="a.py")},
        )
    )
    prompt = parts["prompt"]

    assert parts["task"].startswith("1. First go through every file")
    assert "Every file gets its sentence" in parts["task"]
    assert "step back and judge the change" in parts["task"]
    assert prompt.index("## Your Task") < prompt.index("## How to Review") < prompt.index("## PR Context")
    assert prompt.index("## How to Review") < prompt.index("## Code to Review")
    assert "Do not speculate beyond the shown code" not in prompt
    assert "clearly visible in the provided context" not in prompt
    assert "one bounded review batch" not in prompt
    # The anchor instruction survives the cut: inline comments attach to the snippet.
    assert "copied from the exact added/context line" in parts["task"]


def test_session_notes_are_asked_for_and_parsed_with_caps():
    """`key_facts` and `open_suspicions` are what a continuation would start from and what
    the reviewer sees left open; a request to be brief is not a limit, so they are capped."""
    import json

    from titan_plugin_github.models.review_models import FocusContextBatch
    from titan_plugin_github.operations.findings_operations import (
        SESSION_NOTE_MAX_CHARS,
        SESSION_NOTES_MAX_ITEMS,
        build_findings_prompt_parts,
        findings_json_schema,
        parse_session_notes,
    )

    parts = build_findings_prompt_parts(FocusContextBatch(batch_id="deep_1"))
    assert "`key_facts`" in parts["task"] and "`open_suspicions`" in parts["task"]
    assert '"key_facts"' in parts["schema"]
    assert "open_suspicions" in findings_json_schema()["properties"]

    stdout = json.dumps(
        {
            "findings": [],
            "key_facts": ["  fanout_plan now takes condition  ", "", 3, "x" * 1000],
            "open_suspicions": [f"s{i}" for i in range(SESSION_NOTES_MAX_ITEMS + 5)],
        }
    )
    notes = parse_session_notes(stdout)

    assert notes["key_facts"][0] == "fanout_plan now takes condition"
    assert len(notes["key_facts"]) == 2
    assert len(notes["key_facts"][1]) == SESSION_NOTE_MAX_CHARS
    assert len(notes["open_suspicions"]) == SESSION_NOTES_MAX_ITEMS
    assert parse_session_notes("not json") == {"key_facts": [], "open_suspicions": []}


def test_depth_is_aimed_at_a_focus_chosen_by_criteria_not_by_count():
    """On #273 the session covered 58 files and opened 14-15: depth spread evenly is read
    from the diff. It now picks where a defect does harm, by criteria and with no number,
    goes deep there with named moves, and may not excuse a risky write as "by design"."""
    from titan_plugin_github.models.review_models import FocusContextBatch
    from titan_plugin_github.operations.findings_operations import (
        build_findings_prompt_parts,
        findings_json_schema,
    )

    parts = build_findings_prompt_parts(FocusContextBatch(batch_id="deep_1"))
    task = parts["task"]

    assert "writes to an external system or to production" in task
    assert "As many as the change has, no more" in task
    assert "open it in full" in task and "who consumes its result" in task
    assert "names the function and the case" in task
    # The cheap pass first: left last, it was what the session cut (26/58 on #273).
    assert task.index("without opening") < task.index("choose your focus")
    assert task.index("choose your focus") < task.index("Review each focus file")
    # The two moves a free-form review showed missing on ragnarok #3723.
    assert "report it as an unannounced change when nothing does" in task
    assert "how the rest of the repository does the same thing" in task
    assert "skips a confirmation, a validation or a guard is a finding" in parts["instructions"]
    assert "focus" in findings_json_schema()["required"]
    assert '"focus"' in parts["schema"]


def test_parse_focus_keeps_only_files_the_session_was_handed():
    import json

    from titan_plugin_github.operations.findings_operations import parse_focus

    stdout = json.dumps(
        {
            "focus": [
                {"path": "./src/a.py", "why": "writes to production"},
                {"path": "src/a.py", "why": "duplicate"},
                {"path": "elsewhere.py", "why": "not handed"},
                "not an object",
            ]
        }
    )

    assert parse_focus(stdout, {"src/a.py", "src/b.py"}) == [
        {"path": "src/a.py", "why": "writes to production"}
    ]
    assert parse_focus("nope", {"src/a.py"}) == []


def test_coverage_groups_keep_reading_order_and_never_cut_a_diff():
    from titan_plugin_github.operations.findings_operations import build_coverage_groups

    diffs = {"a.py": "x" * 30, "test_a.py": "y" * 20, "b.py": "z" * 80, "c.py": "w" * 10}

    groups = build_coverage_groups(list(diffs), diffs.get, max_chars=60)

    assert [[path for path, _ in group] for group in groups] == [["a.py", "test_a.py"], ["b.py"], ["c.py"]]


def test_a_coverage_turn_hands_over_every_diff_and_asks_for_every_file():
    from titan_plugin_github.operations.findings_operations import build_coverage_turn_prompt

    prompt = build_coverage_turn_prompt([("a.py", "1 [ADDED] x = 1"), ("b.py", "2 [ADDED] y")], 2, 5)

    assert prompt.startswith("## Code review, group 2 of 5: 2 file(s)")
    assert "### a.py" in prompt and "1 [ADDED] x = 1" in prompt and "### b.py" in prompt
    assert "For EVERY file below give its `reviewed` entry" in prompt
    assert '"reviewed"' in prompt
