"""The triage: call 1 of a review.

What these tests pin is that the triage stays a triage — bounded by characters, scoped to
what it was shown, and publishing nothing.
"""

from titan_plugin_github.models.review_enums import AttentionTier
from titan_plugin_github.operations.triage_operations import (
    build_triage_batches,
    build_triage_prompt_parts,
    parse_triage_notes,
    suspicions_from_notes,
)


def _diff(path: str, added: str = "added line") -> str:
    return (
        f"diff --git a/{path} b/{path}\n"
        "index 111..222 100644\n"
        f"--- a/{path}\n"
        f"+++ b/{path}\n"
        "@@ -1,2 +1,3 @@\n"
        " context\n"
        f"+{added}\n"
        " context\n"
    )


def test_triage_packs_files_until_the_character_budget_says_stop():
    """Characters are the honest unit here: the model cannot read the repo, so the prompt
    IS the spend (D-002)."""
    paths = [f"f{i}.py" for i in range(4)]
    diff = "".join(_diff(path, "x" * 300) for path in paths)

    batches = build_triage_batches(paths, diff, max_prompt_chars=800)

    assert len(batches) > 1
    assert all(batch.tier == AttentionTier.GLANCE for batch in batches)
    assert [batch.batch_id for batch in batches] == [f"triage_{i + 1}" for i in range(len(batches))]
    # Nothing is lost to packing.
    assert {path for batch in batches for path in batch.files_context} == set(paths)


def test_an_ordinary_pr_is_triaged_in_one_call():
    """Ranking and grouping questions means comparing them, which a batch holding two
    files cannot do. With the real budget, PR 3692's shape -- 24 files, ~145k chars of
    diff -- is one batch, not the twelve it was at 18,000 chars."""
    from titan_plugin_github.operations.review_strategy_operations import review_budget

    paths = [f"f{i}.kt" for i in range(24)]
    diff = "".join(_diff(path, added="val x = 1 " * 600) for path in paths)

    batches = build_triage_batches(paths, diff, max_prompt_chars=review_budget().triage_max_prompt_chars)

    assert len(batches) == 1
    assert len(batches[0].files_context) == 24

def test_a_file_whose_diff_exceeds_the_whole_budget_still_gets_triaged():
    """Dropping it would be the silent skip the tiers exist to prevent — it is split
    across passes instead, and every pass holds only that file."""
    diff = _diff("huge.py", "x" * 5000)

    batches = build_triage_batches(["huge.py"], diff, max_prompt_chars=500)

    assert len(batches) > 1
    assert all(list(batch.files_context) == ["huge.py"] for batch in batches)


def test_files_without_diff_hunks_are_not_counted_as_triaged():
    """A binary file or a pure rename has nothing to triage, and calling it covered would
    be a silent skip."""
    batches = build_triage_batches(["binary.png"], _diff("other.py"), 10_000)

    assert batches == []


def test_triage_prompt_asks_for_notes_and_forbids_claims_about_unseen_code():
    paths = ["a.py", "b.py"]
    diff = "".join(_diff(path) for path in paths)
    batch = build_triage_batches(paths, diff, 10_000)[0]

    parts = build_triage_prompt_parts(
        batch,
        pr_intent="Adds passkey support",
    )

    assert "You are TRIAGING, not reviewing" in parts["prompt"]
    assert "Never claim what code outside these hunks does" in parts["prompt"]
    assert "Do not invent a concern" in parts["prompt"]
    # One call over the whole PR must not turn the bar relative: on ragnarok PR #3720 a
    # 32-file call asked 2-3 questions where ten small calls asked 13-16.
    assert "There is no quota" in parts["prompt"]
    assert "you cannot see its replacement in these diffs, ask whether it was migrated or lost" in parts["prompt"]
    assert "Adds passkey support" in parts["prompt"]
    # It must NOT ask for the findings shape: no evidence/severity/anchor vocabulary.
    assert "severity" not in parts["prompt"]
    assert "suggested_comment" not in parts["prompt"]


def test_triage_notes_about_a_file_the_batch_never_saw_are_dropped():
    """Same rule as the deep tier's scope check (cov-002), for the same reason: a note
    about an unseen file would send the deep session looking on no evidence at all."""
    stdout = """{"notes": [
        {"path": "a.py", "note": "Adds a guard", "suspicion": "The guard may invert the check"},
        {"path": "never_shown.py", "note": "Looks wrong", "suspicion": "Everything"},
        {"path": "b.py", "note": "Nothing stands out"}
    ]}"""

    notes = parse_triage_notes(stdout, {"a.py", "b.py"})

    assert [note["path"] for note in notes] == ["a.py", "b.py"]
    assert notes[1]["suspicion"] is None
    assert [item["path"] for item in suspicions_from_notes(notes)] == ["a.py"]


def test_triage_notes_survive_a_bare_array_and_junk():
    """Cheap models are the point of this tier, and they wrap JSON in prose."""
    stdout = 'Here you go:\n[{"path": "a.py", "note": "Fine"}]\nHope that helps!'

    assert parse_triage_notes(stdout, {"a.py"}) == [
        {"path": "a.py", "note": "Fine", "suspicion": None}
    ]


def test_a_diff_too_big_for_one_pass_is_SPLIT_not_truncated():
    """Seeing a quarter of a file and reporting it as triaged is reviewing PART of the
    change and calling it reviewed — the thing this whole domain exists to stop.

    The first implementation truncated (measured: a 2,200-line test file's diff is ~80k
    chars and took a whole call to itself). Splitting keeps coverage honest: each pass is
    told which part it has, and the last part still shares a pass with the files after
    it."""
    hunks_per_file = 40
    big = "".join(
        f"@@ -{1 + i * 40},2 +{1 + i * 40},3 @@\n c\n+{'x' * 900}\n c\n"
        for i in range(hunks_per_file)
    )
    diff = (
        "diff --git a/big.py b/big.py\nindex 1..2 100644\n--- a/big.py\n+++ b/big.py\n"
        + big
        + _diff("small.py")
    )

    batches = build_triage_batches(["big.py", "small.py"], diff, 18_000)

    assert len(batches) == 3
    # Every part of the big file is somewhere, and nothing is silently missing.
    big_hunks = sum(
        len(batch.files_context["big.py"].hunks)
        for batch in batches
        if "big.py" in batch.files_context
    )
    assert big_hunks == hunks_per_file
    # Each pass says which part it holds...
    assert "part 1 of 3" in batches[0].files_context["big.py"].review_hint
    assert "part 3 of 3" in batches[2].files_context["big.py"].review_hint
    # ...and the final part is not wasted on a call of its own.
    assert set(batches[2].files_context) == {"big.py", "small.py"}
    assert all(batch.approximate_chars <= 18_000 for batch in batches)


def test_the_continuation_note_reaches_the_prompt():
    """A pass that does not know it is holding part 2 will happily conclude about the
    parts it never saw."""
    big = "".join(
        f"@@ -{1 + i * 40},2 +{1 + i * 40},3 @@\n c\n+{'x' * 900}\n c\n" for i in range(10)
    )
    diff = "diff --git a/big.py b/big.py\nindex 1..2 100644\n--- a/big.py\n+++ b/big.py\n" + big

    batches = build_triage_batches(["big.py"], diff, 4_000)
    prompt = build_triage_prompt_parts(batches[0])["prompt"]

    assert "did not fit one pass" in prompt
    assert "do not conclude anything about the other parts" in prompt


def test_a_single_hunk_bigger_than_a_whole_pass_is_cut_at_a_line_and_marked():
    """The one unavoidable cut: a new file is ONE hunk covering everything, and nothing
    can send it whole. Every piece still travels — it is cut, not dropped."""
    batches = build_triage_batches(["a.py"], _diff("a.py", "y" * 30_000), 4_000)

    assert len(batches) > 1
    pieces = [
        hunk
        for batch in batches
        for hunk in batch.files_context["a.py"].hunks
    ]
    assert len(pieces) > 1
    assert all("this single hunk is larger" in piece for piece in pieces[:-1])
    assert all(len(piece) <= 4_200 for piece in pieces)



# ---------------------------------------------------------------------------
# What happens to a suspicion after the triage raises it
# ---------------------------------------------------------------------------



# ---------------------------------------------------------------------------
# The settle work moved INTO the deep session (D-014); its tests live with the
# findings prompt now. What stays here is the triage itself.
# ---------------------------------------------------------------------------



def test_a_note_is_capped_in_the_schema_and_again_on_parse():
    """Measured on run `50420f9c`: 59 notes came back as 29,040 output tokens — ~490
    tokens each, paragraphs instead of the one sentence asked for, and MORE output than
    the deep tier's entire review of 40 files. It cost $2.2223 of a $3.6518 review.

    Output is ~95% of what a call bills, so the length of a note IS the price. An
    instruction to be brief is a request; a cap is a fact, and it is enforced twice
    because a CLI without structured output ignores the schema entirely."""
    from titan_plugin_github.operations.triage_operations import (
        TRIAGE_NOTE_MAX_CHARS,
        TRIAGE_SUSPICION_MAX_CHARS,
        parse_triage_notes,
        triage_json_schema,
    )

    properties = triage_json_schema()["properties"]["notes"]["items"]["properties"]
    assert properties["note"]["maxLength"] == TRIAGE_NOTE_MAX_CHARS
    assert properties["suspicion"]["maxLength"] == TRIAGE_SUSPICION_MAX_CHARS

    rambling = "word " * 400
    notes = parse_triage_notes(
        '{"notes":[{"path":"a.py","note":"%s","suspicion":"%s"}]}' % (rambling, rambling),
        {"a.py"},
    )

    assert len(notes[0]["note"]) <= TRIAGE_NOTE_MAX_CHARS
    assert len(notes[0]["suspicion"]) <= TRIAGE_SUSPICION_MAX_CHARS
    assert notes[0]["note"].endswith("…")


def test_a_note_that_already_fits_is_left_exactly_as_written():
    """Trimming a short note would corrupt it for no gain."""
    from titan_plugin_github.operations.triage_operations import parse_triage_notes

    notes = parse_triage_notes(
        '{"notes":[{"path":"a.py","note":"Adds a null guard.","suspicion":null}]}', {"a.py"}
    )

    assert notes == [{"path": "a.py", "note": "Adds a null guard.", "suspicion": None}]


def test_a_multiline_note_is_collapsed_to_one_line():
    """Notes are rendered one per line on screen and one per line in the deep prompt; a
    note with newlines in it breaks both."""
    from titan_plugin_github.operations.triage_operations import parse_triage_notes

    notes = parse_triage_notes(
        '{"notes":[{"path":"a.py","note":"First line.\\n\\n  Second line.","suspicion":null}]}',
        {"a.py"},
    )

    assert notes[0]["note"] == "First line. Second line."
