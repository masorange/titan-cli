"""The triage: call 1 of a review.

Every non-skip file the deep session will NOT open, seen through its diff alone, packed
into as few calls as the character budget allows, on whatever model the user assigned to
`code_review_triage`.

It **publishes nothing**. Its output is working material for the deep session, which
confirms a suspicion by opening the file or drops it. That is what makes this tier cheap
in both senses: a one-line note per file instead of a full analysis, and no obligation to
be right, because something else checks. Over-flagging costs the deep session a look;
under-flagging leaves the file where it already was, which is unlooked-at.

Scope note, and it deviates from the plan on purpose: the triage covers the files the deep
session is not reading, not "every non-skip file in the PR". The deep files' diffs are in
the deep prompt already, so triaging them again would pay twice for the same orientation.
"""

import json
from typing import Any, Optional

from titan_cli.core.logging import get_logger

from ..models.review_enums import AttentionTier, FileReadMode
from .prompt_formatting_operations import pr_description_section
from ..models.review_models import (
    FileContextEntry,
    FocusContextBatch,
    PullRequestManifest,
)

logger = get_logger(__name__)

TRIAGE_BATCH_ID_PREFIX = "triage"

TRIAGE_CONTINUATION_NOTE = (
    "This file's diff did not fit one pass. You are seeing part {part} of {total}; "
    "judge only what is here and do not conclude anything about the other parts."
)
TRIAGE_HUNK_CUT_MARKER = (
    "\n[... this single hunk is larger than one pass can carry and was cut here ...]"
)


def build_triage_batches(
    paths: list[str],
    diff: str,
    max_prompt_chars: int,
    diff_manager=None,
    pr_manifest: Optional[PullRequestManifest] = None,
) -> list[FocusContextBatch]:
    """Pack `paths` into triage batches bounded by characters alone.

    Characters are the honest unit here (D-002): the model cannot read the repo, so the
    prompt IS the spend. The budget is sized so an ordinary PR is ONE batch: ranking and
    grouping questions means comparing them, and a batch that sees two files cannot. More
    than one batch is the fallback for a PR that does not fit, never the plan.

    A file whose diff does not fit one pass is SPLIT across consecutive passes, not
    truncated. Truncating was the first implementation and it was wrong for the reason
    this whole domain exists: seeing a quarter of a 2,200-line file and reporting it as
    triaged is reviewing PART of the change and calling it reviewed. The parts are
    numbered and each pass is told which one it has, so nothing claims to have seen more
    than it did.

    The only unavoidable cut is a SINGLE hunk larger than one whole pass -- a new file is
    one hunk covering everything -- which is cut at a line boundary and marked. Nothing
    can send it whole, and a file shown as nothing cannot be triaged at all.
    """
    from .context_resolution_operations import extract_hunks_only

    batches: list[FocusContextBatch] = []
    current: dict[str, FileContextEntry] = {}
    current_chars = 0
    split_files: dict[str, int] = {}

    def flush() -> None:
        nonlocal current, current_chars
        if not current:
            return
        batches.append(
            FocusContextBatch(
                batch_id=f"{TRIAGE_BATCH_ID_PREFIX}_{len(batches) + 1}",
                tier=AttentionTier.GLANCE,
                files_context=current,
                pr_manifest=pr_manifest,
                approximate_chars=current_chars,
                prompt_budget_target_chars=max_prompt_chars,
            )
        )
        current = {}
        current_chars = 0

    for path in paths:
        hunks = extract_hunks_only(diff, path, diff_manager=diff_manager)
        if not hunks:
            # No diff hunks means nothing to triage: a binary file, a pure rename. Counting
            # it as covered would be the silent skip the tiers exist to prevent.
            continue
        slices = _slice_hunks(hunks, max_prompt_chars)
        if len(slices) > 1:
            split_files[path] = len(slices)
        for part, hunk_slice in enumerate(slices, start=1):
            slice_chars = sum(len(hunk) for hunk in hunk_slice)
            # A path can appear once per batch (the context is keyed by path), so a
            # second part of the same file has to start a new pass. Checked here rather
            # than flushed after every part, so a file's LAST part can still share a
            # pass with the files that follow it.
            if current and (
                path in current
                or current_chars + slice_chars > max_prompt_chars
            ):
                flush()
            current[path] = FileContextEntry(
                path=path,
                read_mode=FileReadMode.HUNKS_ONLY,
                hunks=hunk_slice,
                approximate_chars=slice_chars,
                review_hint=(
                    TRIAGE_CONTINUATION_NOTE.format(part=part, total=len(slices))
                    if len(slices) > 1
                    else ""
                ),
            )
            current_chars += slice_chars

    flush()
    if split_files:
        logger.info(
            "triage_file_diffs_split",
            files=len(split_files),
            parts_per_file=split_files,
            max_prompt_chars=max_prompt_chars,
        )
    logger.info(
        "triage_batches_built",
        paths=len(paths),
        batches=len(batches),
        files=len({path for batch in batches for path in batch.files_context}),
        max_prompt_chars=max_prompt_chars,
        approximate_chars=[batch.approximate_chars for batch in batches],
    )
    return batches


def _slice_hunks(hunks: list[str], budget: int) -> list[list[str]]:
    """Cut a file's hunks into slices that each fit one pass.

    Whole hunks wherever possible: half a hunk reads like complete code and invites a
    note about a guard whose other branch was simply not shown. A single hunk bigger than
    the whole budget is the one case that must be cut mid-hunk, at a line boundary, and
    it is marked so the pass knows what it is looking at.
    """
    slices: list[list[str]] = []
    current: list[str] = []
    used = 0
    for hunk in hunks:
        if len(hunk) > budget:
            if current:
                slices.append(current)
                current, used = [], 0
            slices.extend(_cut_one_hunk(hunk, budget))
            continue
        if current and used + len(hunk) > budget:
            slices.append(current)
            current, used = [], 0
        current.append(hunk)
        used += len(hunk)
    if current:
        slices.append(current)
    return slices or [[]]


def _cut_one_hunk(hunk: str, budget: int) -> list[list[str]]:
    """Split one oversized hunk into line-aligned pieces, each marked as a cut."""
    pieces: list[list[str]] = []
    remaining = hunk
    while remaining:
        if len(remaining) <= budget:
            pieces.append([remaining])
            break
        cut = remaining[:budget]
        boundary = cut.rfind("\n")
        if boundary <= 0:
            boundary = len(cut)
        pieces.append([remaining[:boundary] + TRIAGE_HUNK_CUT_MARKER])
        remaining = remaining[boundary:].lstrip("\n")
    return pieces


# What one note and one suspicion may occupy. Enforced in the schema AND on parse,
# because an instruction to be brief is a request and a cap is a fact.
#
# This exists because of a measurement: on run `50420f9c` the triage produced 29,040 output
# tokens for 59 notes -- ~490 tokens each, paragraphs rather than the one sentence it was
# asked for -- and MORE output than the deep tier's entire review of 40 files. It cost
# $2.2223 of that review's $3.6518. Output is ~95% of what an AI call bills, so the
# length of a note IS the price of the tier.
TRIAGE_NOTE_MAX_CHARS = 200
TRIAGE_SUSPICION_MAX_CHARS = 300

TRIAGE_INSTRUCTIONS = """- You are TRIAGING, not reviewing. One short note per file, and a suspicion only where the diff itself gives you a reason
- A suspicion is a question worth someone opening the file for, not a verdict: something else will open it and confirm or drop it
- BREVITY IS THE POINT: one sentence of at most 25 words per note, and one sentence per suspicion. No code blocks, no quoting the diff back, no lists, no analysis
- You cannot read the repository here. Never claim what code outside these hunks does
- Judge EACH file on its own, as if it were the only one in the list. There is no quota: flagging one file never costs another its question, and a long list is not a reason to flag fewer
- When something is REMOVED or renamed -- a file, a class, a handler, a branch, a field, an event -- and you cannot see its replacement in these diffs, ask whether it was migrated or lost. That is always worth a question
- Do not invent a concern the diff gives no reason for: a file with nothing to ask gets a clean note
- Do not report code style, naming or formatting preferences
- Where a diff says it was truncated, you saw part of the change: note what you saw and do not conclude anything about the rest"""


def build_triage_prompt_parts(
    batch: FocusContextBatch,
    pr_intent: Optional[str] = None,
) -> dict[str, str]:
    """Build the triage prompt, kept separate from the findings prompt on purpose.

    The findings prompt asks for defects with anchors and evidence. Handing that shape to
    a cheap diff-only call is how you get confident claims about code nobody read.
    """
    files_text = _triage_files_to_text(batch.files_context)
    intent = pr_description_section(pr_intent or "")
    pr_line = (
        f"PR #{batch.pr_manifest.number}: {batch.pr_manifest.title}\n"
        if batch.pr_manifest
        else ""
    )
    schema = _triage_schema()

    prompt = f"""You are taking a first pass over part of a pull request.

These files will NOT be read in depth by anyone else unless you flag them. You see only their diffs.

## PR Context
{pr_line}{intent}Batch: {batch.batch_id}
## Diffs
{files_text}

## Instructions
{TRIAGE_INSTRUCTIONS}

Respond ONLY with valid JSON matching this schema. Do not include any prose before or after the JSON.
{schema}
"""
    return {
        "pr_context": f"{pr_line}{intent}",
        "files_context": files_text,
        "instructions": TRIAGE_INSTRUCTIONS,
        "schema": schema,
        "prompt": prompt,
    }


def _triage_files_to_text(files_context: dict) -> str:
    if not files_context:
        return "(no diffs to triage)\n"
    parts: list[str] = []
    for path, entry in files_context.items():
        parts.append(f"### {path}")
        if entry.review_hint:
            parts.append(entry.review_hint)
        for hunk in entry.hunks:
            parts.extend(["```", hunk, "```"])
        parts.append("")
    return "\n".join(parts)


def _triage_schema() -> str:
    return json.dumps(
        {
            "type": "object",
            "properties": {
                "notes": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string"},
                            "note": {
                                "type": "string",
                                "maxLength": TRIAGE_NOTE_MAX_CHARS,
                                "description": "One sentence, 25 words or fewer.",
                            },
                            "suspicion": {
                                "type": ["string", "null"],
                                "maxLength": TRIAGE_SUSPICION_MAX_CHARS,
                                "description": "One sentence on why someone should open this file, or null.",
                            },
                        },
                        "required": ["path", "note"],
                    },
                }
            },
            "required": ["notes"],
        },
        indent=2,
    )


def triage_json_schema() -> dict[str, Any]:
    """Schema for `--json-schema`, so the notes come back as a validated tool call."""
    return json.loads(_triage_schema())


def parse_triage_notes(stdout: str, batch_paths: set[str]) -> list[dict]:
    """Parse triage output into notes, dropping any path the batch was not shown.

    Same rule as the deep tier's scope check (cov-002) and for the same reason: a note
    about a file this call never saw would send the deep session to look at something on
    no evidence at all.
    """
    from titan_cli.core.result import ClientSuccess

    from .ai_response_parsing_operations import extract_json_payload

    # An object with `notes` is the schema; a bare array is what a cheap model returns
    # when it forgets the wrapper, and it is worth accepting rather than losing the pass.
    raw_notes: list = []
    match extract_json_payload(stdout, "object"):
        case ClientSuccess(data=dict() as payload) if payload.get("notes") is not None:
            raw_notes = payload.get("notes") or []
        case _:
            # A bare array is what a cheap model returns when it forgets the wrapper.
            # Tried second because an object search finds the FIRST brace, which on a
            # bare array is the first element rather than the envelope.
            match extract_json_payload(stdout, "array"):
                case ClientSuccess(data=list() as payload):
                    raw_notes = payload
                case _:
                    logger.warning("triage_response_unparseable", chars=len(stdout or ""))

    notes: list[dict] = []
    rejected: list[str] = []
    over_length: list[str] = []
    for item in raw_notes:
        if not isinstance(item, dict):
            continue
        path = (item.get("path") or "").strip()
        note = (item.get("note") or "").strip()
        if not path or not note:
            continue
        if path not in batch_paths:
            rejected.append(path)
            continue
        suspicion = (item.get("suspicion") or "").strip() or None
        # Enforced here too, not only in the schema: a CLI without structured output
        # ignores the schema entirely, and an over-long note is paid for either way --
        # but at least it stops flooding the settle and deep prompts downstream.
        if len(note) > TRIAGE_NOTE_MAX_CHARS or (suspicion and len(suspicion) > TRIAGE_SUSPICION_MAX_CHARS):
            over_length.append(path)
        note = _one_line(note, TRIAGE_NOTE_MAX_CHARS)
        suspicion = _one_line(suspicion, TRIAGE_SUSPICION_MAX_CHARS) if suspicion else None
        notes.append({"path": path, "note": note, "suspicion": suspicion})

    if rejected:
        logger.warning("triage_notes_outside_batch_scope", dropped=len(rejected), paths=sorted(set(rejected)))
    if over_length:
        # Logged rather than silently trimmed: if this fires often the model is ignoring
        # the cap and the tier is paying for prose, which is exactly what made the triage
        # 61% of run `50420f9c`'s bill.
        logger.warning(
            "triage_notes_over_length",
            notes=len(over_length),
            note_cap=TRIAGE_NOTE_MAX_CHARS,
            paths=sorted(set(over_length)),
        )
    return notes


def _one_line(text: str, cap: int) -> str:
    """Collapse to a single line and cut at a word boundary within `cap`."""
    collapsed = " ".join((text or "").split())
    if len(collapsed) <= cap:
        return collapsed
    cut = collapsed[:cap]
    boundary = cut.rfind(" ")
    return (cut[:boundary] if boundary > cap // 2 else cut).rstrip(" ,;:.") + "…"


def suspicions_from_notes(notes: list[dict]) -> list[dict]:
    """The subset the deep session is asked to settle."""
    return [note for note in notes if note.get("suspicion")]
