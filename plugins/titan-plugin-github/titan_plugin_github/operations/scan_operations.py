"""The skim: call 1 of a review.

Every non-skip file the deep session will NOT open, seen through its diff alone, packed
into as few calls as the character budget allows, on whatever model the user assigned to
`code_review_scan`.

It **publishes nothing**. Its output is working material for the deep session, which
confirms a suspicion by opening the file or drops it. That is what makes this tier cheap
in both senses: a one-line note per file instead of a full analysis, and no obligation to
be right, because something else checks. Over-flagging costs the deep session a look;
under-flagging leaves the file where it already was, which is unlooked-at.

Scope note, and it deviates from the plan on purpose: the skim covers the files the deep
session is not reading, not "every non-skip file in the PR". The deep files' diffs are in
the deep prompt already, so skimming them again would pay twice for the same orientation.
"""

import json
from typing import Any, Optional

from titan_cli.core.logging import get_logger

from ..models.review_enums import AttentionTier, FileReadMode
from ..models.review_models import (
    FileContextEntry,
    FocusContextBatch,
    PullRequestManifest,
)

logger = get_logger(__name__)

SCAN_BATCH_ID_PREFIX = "scan"


def build_scan_batches(
    paths: list[str],
    diff: str,
    max_prompt_chars: int,
    max_files_per_batch: int,
    diff_manager=None,
    pr_manifest: Optional[PullRequestManifest] = None,
) -> list[FocusContextBatch]:
    """Pack `paths` into skim batches bounded by characters first.

    Characters are the honest unit here (D-002): the model cannot read the repo, so the
    prompt IS the spend. `max_files_per_batch` is a ceiling against absurdity, not a
    judgement about attention -- the number at which a packed skim goes shallow is O-001,
    still unmeasured, and the risk it guards is bounded because the skim only FLAGS for a
    reader that verifies. A file whose own diff exceeds the whole budget still gets its
    own batch rather than being dropped.
    """
    from .context_resolution_operations import extract_hunks_only

    batches: list[FocusContextBatch] = []
    current: dict[str, FileContextEntry] = {}
    current_chars = 0

    def flush() -> None:
        nonlocal current, current_chars
        if not current:
            return
        batches.append(
            FocusContextBatch(
                batch_id=f"{SCAN_BATCH_ID_PREFIX}_{len(batches) + 1}",
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
            # No diff hunks means nothing to skim: a binary file, a pure rename. Counting
            # it as covered would be the silent skip the tiers exist to prevent.
            continue
        hunks_chars = sum(len(hunk) for hunk in hunks)
        if current and (
            current_chars + hunks_chars > max_prompt_chars
            or len(current) >= max_files_per_batch
        ):
            flush()
        current[path] = FileContextEntry(
            path=path,
            read_mode=FileReadMode.HUNKS_ONLY,
            hunks=hunks,
            approximate_chars=hunks_chars,
        )
        current_chars += hunks_chars

    flush()
    logger.info(
        "scan_batches_built",
        paths=len(paths),
        batches=len(batches),
        files=sum(len(batch.files_context) for batch in batches),
        max_prompt_chars=max_prompt_chars,
        max_files_per_batch=max_files_per_batch,
        approximate_chars=[batch.approximate_chars for batch in batches],
    )
    return batches


SCAN_INSTRUCTIONS = """- You are SKIMMING, not reviewing. One short note per file, and a suspicion only where the diff itself gives you a reason
- A suspicion is a question worth someone opening the file for, not a verdict: something else will open it and confirm or drop it
- You cannot read the repository here. Never claim what code outside these hunks does
- Prefer saying "nothing stands out" over inventing a concern: a file with a clean note is a useful answer
- Do not report code style, naming or formatting preferences
- Keep every note and reason to one sentence"""


def build_scan_prompt_parts(
    batch: FocusContextBatch,
    clusters: Optional[list[dict]] = None,
    pr_intent: Optional[str] = None,
) -> dict[str, str]:
    """Build the skim prompt, kept separate from the findings prompt on purpose.

    The findings prompt asks for defects with anchors and evidence. Handing that shape to
    a cheap diff-only call is how you get confident claims about code nobody read.
    """
    files_text = _scan_files_to_text(batch.files_context)
    clusters_text = _clusters_to_text(clusters or [])
    intent = f"Intent: {pr_intent}\n" if pr_intent else ""
    pr_line = (
        f"PR #{batch.pr_manifest.number}: {batch.pr_manifest.title}\n"
        if batch.pr_manifest
        else ""
    )
    schema = _scan_schema()

    prompt = f"""You are taking a first pass over part of a pull request.

These files will NOT be read in depth by anyone else unless you flag them. You see only their diffs.

## PR Context
{pr_line}{intent}Batch: {batch.batch_id}
{clusters_text}
## Diffs
{files_text}

## Instructions
{SCAN_INSTRUCTIONS}

Respond ONLY with valid JSON matching this schema. Do not include any prose before or after the JSON.
{schema}
"""
    return {
        "pr_context": f"{pr_line}{intent}",
        "clusters": clusters_text,
        "files_context": files_text,
        "instructions": SCAN_INSTRUCTIONS,
        "schema": schema,
        "prompt": prompt,
    }


def _scan_files_to_text(files_context: dict) -> str:
    if not files_context:
        return "(no diffs to skim)\n"
    parts: list[str] = []
    for path, entry in files_context.items():
        parts.append(f"### {path}")
        for hunk in entry.hunks:
            parts.extend(["```", hunk, "```"])
        parts.append("")
    return "\n".join(parts)


def _clusters_to_text(clusters: list[dict]) -> str:
    """Repeated groups, computed deterministically rather than asked for.

    `summarize_candidate_clusters` already knows which paths repeat, so spending model
    output on rediscovering them would be paying for arithmetic. What the model adds is
    whether the repetition is CONSISTENT, which is the question the note asks.
    """
    if not clusters:
        return ""
    lines = "\n".join(
        f"- {cluster['group']}: {cluster['count']} files, e.g. {', '.join(cluster['representatives'])}"
        for cluster in clusters
    )
    return (
        "\n## Repeated Groups (say whether the repetition is consistent across them)\n"
        f"{lines}\n"
    )


def _scan_schema() -> str:
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
                            "note": {"type": "string", "description": "One sentence."},
                            "suspicion": {
                                "type": ["string", "null"],
                                "description": "Why someone should open this file, or null.",
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


def scan_json_schema() -> dict[str, Any]:
    """Schema for `--json-schema`, so the notes come back as a validated tool call."""
    return json.loads(_scan_schema())


def parse_scan_notes(stdout: str, batch_paths: set[str]) -> list[dict]:
    """Parse skim output into notes, dropping any path the batch was not shown.

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
                    logger.warning("scan_response_unparseable", chars=len(stdout or ""))

    notes: list[dict] = []
    rejected: list[str] = []
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
        notes.append({"path": path, "note": note, "suspicion": suspicion})

    if rejected:
        logger.warning("scan_notes_outside_batch_scope", dropped=len(rejected), paths=sorted(set(rejected)))
    return notes


def suspicions_from_notes(notes: list[dict]) -> list[dict]:
    """The subset the deep session is asked to settle."""
    return [note for note in notes if note.get("suspicion")]
