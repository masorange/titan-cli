"""The skim: call 1 of a review.

What these tests pin is that the skim stays a skim — bounded by characters, scoped to
what it was shown, and publishing nothing.
"""

from titan_plugin_github.models.review_enums import AttentionTier
from titan_plugin_github.operations.scan_operations import (
    build_scan_batches,
    build_scan_prompt_parts,
    parse_scan_notes,
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


def test_scan_packs_files_until_the_character_budget_says_stop():
    """Characters are the honest unit here: the model cannot read the repo, so the prompt
    IS the spend (D-002)."""
    paths = [f"f{i}.py" for i in range(4)]
    diff = "".join(_diff(path, "x" * 300) for path in paths)

    batches = build_scan_batches(paths, diff, max_prompt_chars=800, max_files_per_batch=10)

    assert len(batches) > 1
    assert all(batch.tier == AttentionTier.GLANCE for batch in batches)
    assert [batch.batch_id for batch in batches] == [f"scan_{i + 1}" for i in range(len(batches))]
    # Nothing is lost to packing.
    assert {path for batch in batches for path in batch.files_context} == set(paths)


def test_scan_respects_the_per_batch_file_ceiling():
    """A prompt that fits the char budget can still hold more files than one pass can
    judge. The number at which that happens is unmeasured (O-001), so this is a ceiling
    against absurdity, not a claim about attention."""
    paths = [f"f{i}.py" for i in range(5)]
    diff = "".join(_diff(path) for path in paths)

    batches = build_scan_batches(paths, diff, max_prompt_chars=100_000, max_files_per_batch=2)

    assert [len(batch.files_context) for batch in batches] == [2, 2, 1]


def test_a_file_whose_diff_exceeds_the_whole_budget_still_gets_skimmed():
    """Dropping it would be the silent skip the tiers exist to prevent."""
    diff = _diff("huge.py", "x" * 5000)

    batches = build_scan_batches(["huge.py"], diff, max_prompt_chars=500, max_files_per_batch=10)

    assert len(batches) == 1
    assert list(batches[0].files_context) == ["huge.py"]


def test_files_without_diff_hunks_are_not_counted_as_skimmed():
    """A binary file or a pure rename has nothing to skim, and calling it covered would
    be a silent skip."""
    batches = build_scan_batches(["binary.png"], _diff("other.py"), 10_000, 10)

    assert batches == []


def test_scan_prompt_asks_for_notes_and_forbids_claims_about_unseen_code():
    paths = ["a.py", "b.py"]
    diff = "".join(_diff(path) for path in paths)
    batch = build_scan_batches(paths, diff, 10_000, 10)[0]

    parts = build_scan_prompt_parts(
        batch,
        clusters=[{"group": "adapters", "count": 4, "representatives": ["a.py", "b.py"]}],
        pr_intent="Adds passkey support",
    )

    assert "You are SKIMMING, not reviewing" in parts["prompt"]
    assert "Never claim what code outside these hunks does" in parts["prompt"]
    assert "Prefer saying \"nothing stands out\"" in parts["prompt"]
    # The repeated groups are computed deterministically and handed over, not asked for.
    assert "adapters: 4 files" in parts["prompt"]
    assert "Adds passkey support" in parts["prompt"]
    # It must NOT ask for the findings shape: no evidence/severity/anchor vocabulary.
    assert "severity" not in parts["prompt"]
    assert "suggested_comment" not in parts["prompt"]


def test_scan_notes_about_a_file_the_batch_never_saw_are_dropped():
    """Same rule as the deep tier's scope check (cov-002), for the same reason: a note
    about an unseen file would send the deep session looking on no evidence at all."""
    stdout = """{"notes": [
        {"path": "a.py", "note": "Adds a guard", "suspicion": "The guard may invert the check"},
        {"path": "never_shown.py", "note": "Looks wrong", "suspicion": "Everything"},
        {"path": "b.py", "note": "Nothing stands out"}
    ]}"""

    notes = parse_scan_notes(stdout, {"a.py", "b.py"})

    assert [note["path"] for note in notes] == ["a.py", "b.py"]
    assert notes[1]["suspicion"] is None
    assert [item["path"] for item in suspicions_from_notes(notes)] == ["a.py"]


def test_scan_notes_survive_a_bare_array_and_junk():
    """Cheap models are the point of this tier, and they wrap JSON in prose."""
    stdout = 'Here you go:\n[{"path": "a.py", "note": "Fine"}]\nHope that helps!'

    assert parse_scan_notes(stdout, {"a.py"}) == [
        {"path": "a.py", "note": "Fine", "suspicion": None}
    ]
