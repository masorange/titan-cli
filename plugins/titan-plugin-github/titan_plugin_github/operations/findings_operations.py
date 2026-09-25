"""Operations for building AI prompts for focused findings review."""

import json
import re
from typing import Any, Callable, Optional

from titan_cli.core.result import ClientError, ClientResult, ClientSuccess

from ..models.review_models import Finding, FocusContextBatch, ReviewChecklistItem
from .ai_response_parsing_operations import extract_json_payload
from .prompt_formatting_operations import (
    comment_context_to_json,
    pr_description_section,
    review_pr_description,
)


def build_findings_prompt_parts(batch: FocusContextBatch) -> dict[str, str]:
    """Build prompt parts separately so callers can log size breakdowns."""
    checklist_json = _checklist_to_json(batch.checklist_applicable)
    comments_json = comment_context_to_json(batch.comment_context)
    files_text = _files_context_to_text(batch.files_context)
    related_text = _related_files_to_text(batch.related_files)
    pr_context = _pr_context_to_text(batch)
    schema = _finding_schema()

    has_shape = bool(batch.change_shape)
    on_disk = any(entry.on_disk for entry in batch.files_context.values())

    # The task and the deliverable come FIRST. They used to be one line among ~20
    # instructions after 339k chars of diffs, and on #236 (run 7d61a0b9) the session
    # accounted for 32 of 58 deep files: it reviewed by hypothesis, opened what looked
    # suspicious and left the read-only steps, prompts and YAML unmentioned. Coverage is
    # the job, so it is stated as the job, before the material it applies to.
    #
    # And depth is AIMED, not spread. Covering every file made the session say something
    # about each of 58 (runs a51b2734 / bfd570ac on #273) while opening only 14-15 of them:
    # its effort is roughly fixed, and spread evenly it reads everything from the diff.
    # Each important it missed needed one move -- an edge case, a consequence, a consumer --
    # applied to the right file. So it first chooses where a defect would do harm, by
    # criteria rather than by count (a count misses the dangerous files of a large PR and
    # pads a small one), and spends its depth there.
    #
    # The cheap pass comes FIRST. With depth first, the one-line pass over the rest was
    # what got cut when the session judged itself done (26 of 58 accounted on #273, run
    # 88e6c190); from the diff it costs a sentence per file and no tool call, so nothing
    # is saved by leaving it last.
    #
    # Two moves were added after a free-form review of ragnarok #3723 found 10 defects the
    # session missed, all of one of two kinds: a behaviour the old code had that the new
    # one silently drops, and a departure from how the rest of the repository does the
    # same thing (a missing path prefix every sibling API has, in a file it had in focus).
    # A PR exists to change behaviour, so a change is only a finding when nothing in the
    # PR announces it.
    steps: list[str] = [
        'First go through every file under "Code to Review" from its diff'
        + (
            " (the whole diff is in `.titan-review/pr.diff`, each file's in the path under it)"
            if on_disk
            else ""
        )
        + ", without opening the source, and write its sentence in `reviewed`: what it changes, and whether "
        "anything in it needs a closer look. Every file gets its sentence; a file missing "
        "from `reviewed` reads as a file nobody looked at. Files flagged by the triage are "
        "the exception: settling their question is their account.",
        "Then choose your focus: every file where a defect would do real harm -- it writes "
        "to an external system or to production, handles authentication or secrets, "
        "transforms or converts data, or changes a contract other code relies on. As many "
        "as the change has, no more. List them in `focus`, each with the reason.",
        "Review each focus file in depth: open it in full and, for every changed function, "
        "check its inputs (what can arrive null, empty or unexpected -- look at the type), "
        "its edge cases, what happens in production when it goes wrong, and who consumes its "
        "result (search the callers). Check also what it no longer does: for every behaviour "
        "the diff removes or changes"
        + (" (its base version shows how it worked before)" if on_disk else "")
        + ", look for the PR description, a project document or a "
        "new test that announces it, and report it as an unannounced change when nothing "
        "does"
        + (
            "; such a finding puts in `old_code` the line of the base version that had the "
            "behaviour, copied exactly -- it is checked against the base version and the new "
            "file, and dropped if the line is not in the base or is still in the new file"
            if on_disk
            else ""
        )
        + ". And check how the rest of the repository does the same thing: find one or two "
        "files that do the same job and report where this one departs from them without a "
        "reason. Its `reviewed` sentence names the function and the case you checked.",
    ]
    # The questions the triage raised are a SECOND task list, and they come after the
    # review: a question like "no test covers the magic-link path" is answered far
    # better by whoever just read the magic-link code. Asked first, they set the agenda:
    # across three runs of PR 3692, 5-6 of 8 findings were confirmed triage questions while
    # the serious defects in the deep files came and went.
    if batch.triage_suspicions:
        steps.append(
            'Then settle each question under "Questions from the triage", using what that '
            "review taught you."
        )
    # Only a batch that carries the whole change's shape can judge the change as a whole;
    # a timeout retry holds a few files and nothing else.
    if has_shape:
        steps.append(
            "Last, step back and judge the change, not just the lines: does it do what the "
            "PR says, does it break something that worked, is anything it needed missing?"
        )
    steps.append(
        "Report each problem as a finding, with the code that proves it in `evidence` and a "
        "short `snippet` copied from the exact added/context line the comment should anchor "
        "to (null only if no stable inline anchor exists). No findings is a valid answer: "
        "return an empty `findings` list."
    )
    # What a later reader of this review needs and would otherwise have to re-derive: the
    # facts the session established while reading, and what it suspected but did not
    # settle. Asked of every session so that anything picking up what it left unreviewed
    # starts from them, and shown so the reviewer sees what was left open.
    steps.append(
        "Finally, write in `key_facts` what you established that someone continuing this "
        "review would need (a contract that changed, who calls what, what a flag controls), "
        "and in `open_suspicions` what you suspected but could not settle, naming the file. "
        "One sentence each; both may be empty."
    )
    task = "\n".join(f"{index}. {step}" for index, step in enumerate(steps, start=1))

    rules: list[str] = []
    # Asked explicitly, and only when the batch holds more than one file, because a
    # session that CAN see several files together does not necessarily go looking: the
    # separate synthesis call on run 4fd7f345 found mismatched credential labels and a
    # duplicated redaction policy that a session holding all seven files had not reported.
    if len(batch.files_context) > 1:
        rules.append(
            "These files are one change. Look for contract mismatches ACROSS them (a "
            "signature, return shape, field, event or error contract changed in one while "
            "a caller or consumer in another still uses the old one), a change applied in "
            "some and missed in others, and the same concept named or treated differently"
        )
    rules.append(
        "Before asserting what happens in a configuration, flavor, environment or call site "
        "that is NOT in the diff, open it in the working tree and check. If you cannot check "
        "it, say what you verified and what you assumed"
    )
    # Absences are where the serious defects hide: all three blocking items a
    # free-form session found on ragnarok #3692 were absences, and the session had the
    # tools to check them -- nothing told it to look.
    rules.append(
        "Before reporting that something is MISSING, unused, untested, unhandled or not "
        "overridden anywhere, SEARCH the working tree for it first (Grep and Glob are "
        "available and recursive) and put what the search returned in `evidence`. An "
        "absence claimed without a search is a guess. The same goes for a removal: a deleted "
        "line is not a finding by itself, but what its removal BREAKS is -- behaviour with no "
        "replacement, a caller or event left without its handler, a guarantee the old code "
        "gave. SEARCH for the replacement before claiming it, and anchor such a finding on a "
        "remaining line near the removal, or use a null `snippet`"
    )
    # "By design" was how a session that SAW a production write skip its confirmation
    # (create_key_step on #273, both runs) talked itself out of reporting it.
    rules.append(
        "Do not excuse a risky behaviour as intended because the code does it on purpose: a "
        "write to production or to an external system that skips a confirmation, a "
        "validation or a guard is a finding, unless a comment, a document or a test in the "
        "repository states that it is intended"
    )
    rules.append(
        "Report only what has an observable impact: correctness, error handling, security, "
        "validation, API contracts, concurrency, state consistency; a change in what data, "
        "events, labels or results MEAN, or in how faithfully they are recorded, converted "
        "or shown, even if the code still runs; a guarantee the old code gave that is gone "
        "(success/failure signalling, a fallback); missing regression coverage where clearly "
        "required. Not style, naming, refactor or architecture preferences"
    )
    # Bounded by cost, not by count: on #273 the 8 questions took about half of the
    # session's exploration and none was confirmed, but in a PR with little deep code the
    # questions are most of the coverage, so capping how many would lose exactly there.
    if batch.triage_suspicions:
        rules.append(
            "Settling a triage question: open the flagged file and decide with one or two "
            "lookups. Report a finding only when you can point at the code that makes the "
            "claim true. \"This is fine\" is a complete and expected answer: put it in "
            "`dismissed` with one sentence on what you checked. If one or two lookups do not "
            "settle it, stop and put it in `open_suspicions` rather than searching on: the "
            "focus files need that time. A defect you SEE in a flagged file, on the question "
            "or not, is a finding like any other"
        )
    instructions = "\n".join(f"- {rule}" for rule in rules) + "\n"

    material_text = _review_material_to_text() if on_disk else ""
    if on_disk:
        # The comments are in pr.md with the rest of the PR; the prompt only says so.
        comments_json = "In `.titan-review/pr.md`."
    shape_text = _change_shape_to_text(batch, on_disk=on_disk)
    context_docs_text = _context_docs_to_text(batch)
    suspicions_text = _triage_suspicions_to_text(batch)
    # A batch that carries the whole change's shape is THE review, not a slice of one, and
    # it is told so: the framing decides whether the model reports what it can see in the
    # files it was handed or judges the change as a whole against what the PR claims.
    opening = (
        "Review this pull request. The files that matter are open to you in the working "
        "tree, and you have the shape of the whole change."
        if has_shape
        else "Review the files below. They are part of a larger pull request; report the "
        "problems actually present in them."
    )

    prompt = f"""You are performing a pull request code review.

{opening}

## Your Task
{task}

## How to Review
{instructions}
## PR Context
{pr_context}
{material_text}{context_docs_text}{shape_text}
## Existing Comments (do not duplicate these)
{comments_json}

## Review Axes
{checklist_json}

## Code to Review
{files_text}{related_text}
{suspicions_text}
Respond ONLY with a valid JSON object of this shape. Do not include any prose before or after the JSON.
{schema}
"""

    return {
        "pr_context": pr_context,
        "change_shape": shape_text,
        "context_docs": context_docs_text,
        "triage_suspicions": suspicions_text,
        "comments": comments_json,
        "review_axes": checklist_json,
        "files_context": files_text,
        "related_context": related_text,
        "task": task,
        "instructions": instructions,
        "schema": schema,
        "prompt": prompt,
    }


def _review_material_to_text() -> str:
    """Where the material is, when it is files in the worktree rather than the prompt."""
    from .review_material_operations import BASE_DIR, DIFFS_DIR, PR_FILE, WHOLE_DIFF_FILE

    return (
        "\n## Review Material (files in the working tree, read them as you need them)\n"
        f"- `{PR_FILE}`: the PR description and the review comments already posted\n"
        f"- `{WHOLE_DIFF_FILE}`: the whole diff, every line numbered and labelled "
        "[ADDED] / [CONTEXT] / [DELETED]\n"
        f"- `{DIFFS_DIR}/<path>.diff`: the same, one file per changed file\n"
        f"- `{BASE_DIR}/<path>`: each changed file as it was before this PR\n"
        "The source under review is the working tree itself. The review folder is hidden, so "
        "a search of the tree does not include it: search it by its path when you mean to.\n"
    )


def _triage_suspicions_to_text(batch: FocusContextBatch) -> str:
    """What the triage flagged, and what this session is asked to do about it."""
    if not batch.triage_suspicions:
        return ""
    lines = "\n".join(
        f"- {item.get('path')}: {item.get('suspicion')}" for item in batch.triage_suspicions
    )
    return (
        "\n## Questions from the triage (a SECOND task, for AFTER the review above)\n"
        "A cheap pass over the rest of the PR saw only these files' diffs and raised these "
        "questions. Each names a file that is NOT part of the review above. Review the code "
        "above first; then, with what it taught you, open each file, decide, and either "
        "report a finding with the code that proves it or dismiss it saying what you "
        "checked. A question you cannot settle is not a finding.\n"
        f"{lines}\n"
    )


def _context_docs_to_text(batch: FocusContextBatch) -> str:
    """The project's own rules, by path. Empty string when none were resolved."""
    if not batch.context_docs:
        return ""
    lines = "\n".join(f"- {path}" for path in batch.context_docs)
    return (
        "\n## Project Context (consult before judging; do NOT read end to end)\n"
        "These state how this project does things. Where they contradict general good "
        "practice, they win: a convention the project chose on purpose is not a finding, "
        "and breaking one IS.\n"
        "Look up only what bears on the files below — the rules for their area, the "
        "conventions they follow — and stop there. Reading these in full is not the job "
        "and spends the review's time on documentation instead of code.\n"
        f"{lines}\n"
    )


def _change_shape_to_text(batch: FocusContextBatch, on_disk: bool = False) -> str:
    """The checklist: every changed file and who covers it — no content. Empty when absent."""
    if not batch.change_shape:
        return ""
    lines = "\n".join(batch.change_shape)
    others = (
        "Every other row was left out by rule (lockfiles, renames, deletions, static "
        "resources); its diff is in the review folder if a question needs it."
        if on_disk
        else "Every other row was read by the triage from its diff alone, and its note is "
        "context, not a verdict: any of those files is in the working tree if a question "
        "needs it."
    )
    return (
        "\n## Checklist (every changed file in this PR)\n"
        "Rows marked YOU are your tasks: the files under \"Code to Review\" and the triage "
        f"questions. {others}\n"
        f"{lines}\n"
    )


def _pr_context_to_text(batch: FocusContextBatch) -> str:
    if not batch.pr_manifest:
        return f"Batch {batch.batch_id}"
    pr = batch.pr_manifest
    intent = batch.pr_intent or review_pr_description(pr.description)
    return (
        f"PR #{pr.number}: {_short_title(pr.title)}\n"
        f"{pr.base} -> {pr.head}\n"
        f"Batch: {batch.batch_id}\n"
        + pr_description_section(intent)
    )


_CHECKLIST_DESCRIPTION_CAP = 200
"""Hard cap per checklist description in the findings prompt.

The cap stays because a description is a prompt line, not an essay, and a project can
write a paragraph into its checklist. The number of ITEMS is no longer capped: 12 axes at
this cap is ~2.4k chars against a 120,000-char budget, and cutting them cost a credentials
PR its `security` axis (run `70777691`)."""


def _checklist_to_json(checklist: list[ReviewChecklistItem]) -> str:
    return json.dumps(
        [
            {
                "id": str(item.id),
                "name": item.name,
                "description": item.description[:_CHECKLIST_DESCRIPTION_CAP],
            }
            # No cut here: the plan already decided which axes apply. This was the SAME
            # `[:4]` as `select_review_axes`, applied a second time in the renderer, so
            # even a plan that selected 8 axes could only ever ask about 4.
            for item in checklist
        ],
        indent=2,
    )
def _files_context_to_text(files_context: dict) -> str:
    if not files_context:
        return "(no files to review)\n"

    parts: list[str] = []
    for path, entry in files_context.items():
        parts.append(f"### {path}")
        if entry.on_disk:
            parts.append(entry.review_hint)
            parts.append("")
            continue
        if entry.worktree_reference:
            parts.append("Open this file in the working tree; the diff below is what changed.")
            if entry.review_hint:
                parts.append(entry.review_hint)
            if entry.changed_hunk_headers and not entry.hunks:
                parts.append("Changed regions to inspect first:")
                parts.extend(f"- {header}" for header in entry.changed_hunk_headers)
            # The diff stays inline even though the file is on disk: the working tree holds
            # the post-change file, so "what changed" is not recoverable from it, and the
            # added lines are what an inline comment anchors to.
            for hunk in entry.hunks:
                parts.append("```")
                parts.append(_annotate_diff_hunk(hunk))
                parts.append("```")
        elif entry.full_content:
            parts.append("```")
            parts.append(_add_line_numbers(entry.full_content))
            parts.append("```")
        elif entry.expanded_hunks:
            for hunk in entry.expanded_hunks:
                parts.append("```")
                parts.append(_annotate_diff_hunk(hunk))
                parts.append("```")
        else:
            for hunk in entry.hunks:
                parts.append("```")
                parts.append(_annotate_diff_hunk(hunk))
                parts.append("```")
        parts.append("")
    return "\n".join(parts)


def _related_files_to_text(related_files: dict[str, str]) -> str:
    if not related_files:
        return ""
    parts = ["\n## Related Context"]
    for label, content in related_files.items():
        parts.append(f"\n### {label}")
        # A one-line pointer is not code; fencing it just adds noise. Whole-file content
        # (only sent when the working tree cannot be trusted) still gets a fence.
        if "\n" in content:
            parts.extend(["```", content[:2000], "```"])
        else:
            parts.append(content)
    return "\n".join(parts) + "\n"


def _add_line_numbers(content: str) -> str:
    lines = content.splitlines()
    width = len(str(len(lines)))
    return "\n".join(f"{str(i + 1).rjust(width)} | {line}" for i, line in enumerate(lines))


_DIFF_HUNK_MARKER = "# --- diff hunk ---"


def _annotate_diff_hunk(hunk: str) -> str:
    lines = hunk.splitlines()
    if not lines:
        return ""

    new_line_start = None
    header_line = None
    for line in lines:
        if line.startswith("@@"):
            header_line = line
            match = re.search(r"\+(\d+)", line)
            if match:
                new_line_start = int(match.group(1))
            break

    if new_line_start is None:
        return "\n".join(lines)

    # `expanded_hunks` entries (DiffContextManager.build_expanded_hunks) prepend a
    # "surrounding context" block of raw file lines (no diff +/-/space prefixes) before the
    # real diff hunk. Only the portion after the marker is actual diff content — annotating
    # the preamble too would misread indented raw code lines as numbered [CONTEXT] diff lines
    # and corrupt the line counter for everything that follows.
    preamble: list[str] = []
    diff_lines = lines
    if _DIFF_HUNK_MARKER in lines:
        marker_idx = lines.index(_DIFF_HUNK_MARKER)
        preamble = lines[: marker_idx + 1]
        diff_lines = lines[marker_idx + 1 :]

    result = list(preamble) if preamble else ([header_line] if header_line else [])
    current_line = new_line_start
    width = len(str(current_line + 100))

    for line in diff_lines:
        if line.startswith("@@"):
            continue
        if line.startswith("---") or line.startswith("+++"):
            result.append(line)
        elif line.startswith("-"):
            # Removed code is what a migration or refactor can lose, so it is labelled,
            # not hidden: "do not review" here made the session skip exactly the removal
            # of two analytics reducers whose actions are still dispatched (PR #3720).
            result.append(f"[DELETED] {line[1:]}")
        elif line.startswith("+"):
            result.append(f"{str(current_line).rjust(width)} [ADDED] {line[1:]}")
            current_line += 1
        elif line.startswith(" "):
            result.append(f"{str(current_line).rjust(width)} [CONTEXT] {line[1:]}")
            current_line += 1
        else:
            result.append(line)
    return "\n".join(result)


def _finding_schema() -> str:
    """The response shape the prompt asks for, as text, for CLIs without a schema flag.

    The same `{findings, dismissed}` object `findings_json_schema()` enforces where the
    CLI can. It used to be a bare findings array, which left a model with nowhere to
    write "checked, it is fine": on run bcee6ab3 codex answered all 9 triage questions
    implicitly and every one showed as UNANSWERED.
    """
    return json.dumps(
        {
            "findings": [
                {
                "severity": "<blocking|important|nit>",
                "category": "<problem category>",
                "path": "<file path>",
                "line": "<line or null>",
                "title": "<short actionable title>",
                "why": "<why this is a problem>",
                "evidence": "<exact supporting snippet>",
                "snippet": "<short anchor snippet from the target line or null>",
                "old_code": "<for a behaviour the PR drops: the base-version line that had it, else null>",
                "suggested_comment": "<ready-to-post GitHub review comment>",
                }
            ],
            "dismissed": [
                {
                    "path": "<file a triage question named>",
                    "reason": "<one sentence: what you checked, or why you could not>",
                }
            ],
            "reviewed": [
                {
                    "path": "<every file under Code to Review>",
                    "note": "<one sentence: what you checked, or why you could not judge it>",
                }
            ],
            "focus": [
                {
                    "path": "<a file under Code to Review where a defect would do real harm>",
                    "why": "<one sentence: the harm>",
                }
            ],
            "key_facts": ["<one sentence someone continuing this review would need>"],
            "open_suspicions": ["<one sentence: what you suspected and could not settle, and where>"],
        },
        indent=2,
    )


FINDINGS_DISALLOWED_TOOLS = ("Bash", "Edit", "Write", "NotebookEdit", "WebFetch", "WebSearch", "Agent")
"""Tools removed from the CLI's session for `ai_review_findings` calls.

A findings-review call never needs to modify files, fetch the web, or spawn a subagent, and
`Bash` is the exact vector traced (D-011) to unbounded, mostly unproductive exploration —
recursive shell greps/finds across whole directory trees, not scoped to the worktree the way
`Read`/`Grep`/`Glob` are. Those three stay available: they cover the same legitimate
cross-file lookups (an imported type, a caller, a test) through Claude Code's own bounded
tools instead of arbitrary shell recursion.
"""

FINDINGS_WORKTREE_REFERENCE_EFFORT = "high"
"""Reasoning-effort tier for findings batches that read files from the worktree.

It was "medium", and that was the right answer to a different question. Capping effort was
a per-file cost mitigation: with one session per deep file, a real replay showed medium cut
one file's review from ~330s/$1.10 to ~170s/$0.78 while still finding a genuine bug ("low"
was faster still, ~50s/$0.34, and missed it). Multiplied across nine files that saving was
worth having.

The deep tier is now one session over all of them, which changes the arithmetic: measured
2026-09-22 over the same ten files of PR 251, medium returned 5 findings in 4 files for
$2.1809 and high returned 7 in 5 for $2.5215 -- two of them defects medium did not report.
Thirty-four cents for two real findings is a trade worth making when it is paid once per
review instead of once per file, and both figures are a fraction of the $7.4581 that nine
capped-effort sessions cost on the same PR.
"""


def findings_json_schema() -> dict[str, Any]:
    """JSON Schema for `--json-schema`, enforcing findings as a tool call instead of
    relying on the model to follow a "respond only with JSON" prompt instruction.

    Wrapped in an object because Anthropic's structured-output tool schema requires a
    top-level "object" type; the array of findings lives under the "findings" key.
    """
    return {
        "type": "object",
        "properties": {
            "findings": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "severity": {"type": "string", "enum": ["blocking", "important", "nit"]},
                        "category": {"type": "string"},
                        "path": {"type": "string"},
                        "line": {"type": ["integer", "null"]},
                        "title": {"type": "string"},
                        "why": {"type": "string"},
                        "evidence": {"type": "string"},
                        "snippet": {"type": ["string", "null"]},
                        "old_code": {"type": ["string", "null"]},
                        "suggested_comment": {"type": "string"},
                    },
                    "required": ["severity", "category", "path", "title", "why", "evidence", "suggested_comment"],
                },
            },
            "dismissed": {
                "type": "array",
                "description": (
                    "Questions from the triage you checked and found unfounded, or "
                    "could not check. Empty when none were asked."
                ),
                "items": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string"},
                        "reason": {"type": "string", "description": "One sentence."},
                    },
                    "required": ["path", "reason"],
                },
            },
            "reviewed": {
                "type": "array",
                "description": (
                    "Every file under Code to Review except the ones the triage flagged, each "
                    "with one sentence on what was checked or why it could not be judged."
                ),
                "items": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string"},
                        "note": {"type": "string", "description": "One sentence."},
                    },
                    "required": ["path", "note"],
                },
            },
            "focus": {
                "type": "array",
                "description": "Files where a defect would do real harm, each with why.",
                "items": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string"},
                        "why": {"type": "string", "description": "One sentence."},
                    },
                    "required": ["path", "why"],
                },
            },
            "key_facts": {
                "type": "array",
                "description": "What someone continuing this review would need. One sentence each.",
                "items": {"type": "string"},
            },
            "open_suspicions": {
                "type": "array",
                "description": "What was suspected and not settled, naming the file. One sentence each.",
                "items": {"type": "string"},
            },
        },
        # `reviewed` is the coverage ledger: without it a session handed 58 files could
        # read a dozen and return, and nothing would say which ones it skipped (PR #236,
        # run 3c8aadad: four important defects in files that entered the prompt unread).
        # Both sides required, deliberately. A findings-only schema teaches the model that
        # "this is fine" is not an answer, and then a dismissed question is
        # indistinguishable from an ignored one -- which is how the verification pass this
        # replaces refuted 0 findings in four real runs while confirming a known false
        # positive twice.
        "required": ["findings", "dismissed", "focus", "reviewed", "key_facts", "open_suspicions"],
    }


def parse_dismissals(stdout: str, allowed_paths: set[str]) -> list[dict]:
    """The `dismissed` side of a findings response, scoped to what was actually asked.

    A dismissal of a file nobody flagged is as unfounded as a finding about one (cov-002),
    and it would corrupt the accounting that tells a deliberate dismissal from silence.
    """
    match extract_json_payload(stdout, kind="object"):
        case ClientSuccess(data=payload) if isinstance(payload, dict):
            allowed = {normalize_finding_path(path) for path in allowed_paths}
            kept = []
            for item in payload.get("dismissed") or []:
                if not isinstance(item, dict):
                    continue
                path = normalize_finding_path((item.get("path") or "").strip())
                if path and path in allowed:
                    kept.append({"path": path, "reason": (item.get("reason") or "").strip()})
            return kept
        case _:
            return []


def parse_reviewed_files(stdout: str, allowed_paths: set[str]) -> list[dict]:
    """The `reviewed` ledger of a findings response, scoped to the files that were handed.

    An entry for a file the session was not given is dropped for the same reason a
    dismissal of an unflagged file is: it would count coverage that did not happen.
    Repeated paths keep their first note.
    """
    match extract_json_payload(stdout, kind="object"):
        case ClientSuccess(data=payload) if isinstance(payload, dict):
            allowed = {normalize_finding_path(path) for path in allowed_paths}
            kept: dict[str, str] = {}
            for item in payload.get("reviewed") or []:
                if not isinstance(item, dict):
                    continue
                path = normalize_finding_path((item.get("path") or "").strip())
                if path and path in allowed and path not in kept:
                    kept[path] = (item.get("note") or "").strip()
            return [{"path": path, "note": note} for path, note in kept.items()]
        case _:
            return []


SESSION_NOTES_MAX_ITEMS = 20
SESSION_NOTE_MAX_CHARS = 400


def parse_focus(stdout: str, allowed_paths: set[str]) -> list[dict]:
    """The files the session chose to review in depth, scoped to what it was handed.

    Recorded so a missed defect can be placed: inside the focus it is a depth problem,
    outside it the criteria chose wrong.
    """
    allowed = {normalize_finding_path(path): path for path in allowed_paths}
    focus: list[dict] = []
    match extract_json_payload(stdout, kind="object"):
        case ClientSuccess(data=payload) if isinstance(payload, dict):
            for item in payload.get("focus") or []:
                if not isinstance(item, dict):
                    continue
                path = allowed.get(normalize_finding_path(str(item.get("path") or "")))
                if path and all(entry["path"] != path for entry in focus):
                    focus.append(
                        {"path": path, "why": str(item.get("why") or "").strip()[:SESSION_NOTE_MAX_CHARS]}
                    )
        case _:
            pass
    return focus


def parse_session_notes(stdout: str) -> dict[str, list[str]]:
    """The `key_facts` and `open_suspicions` of a findings response, capped.

    Capped on parse because a request to be brief is not a limit, and both lists are
    rendered and carried forward.
    """
    notes: dict[str, list[str]] = {"key_facts": [], "open_suspicions": []}
    match extract_json_payload(stdout, kind="object"):
        case ClientSuccess(data=payload) if isinstance(payload, dict):
            for key in notes:
                items = payload.get(key)
                if not isinstance(items, list):
                    continue
                notes[key] = [
                    item.strip()[:SESSION_NOTE_MAX_CHARS]
                    for item in items
                    if isinstance(item, str) and item.strip()
                ][:SESSION_NOTES_MAX_ITEMS]
        case _:
            pass
    return notes


def parse_findings_response(stdout: str, *, structured: bool) -> ClientResult[list]:
    """Parse a findings-batch CLI response.

    When `structured` is True (the adapter enforced `findings_json_schema()`), stdout is
    the schema envelope `{"findings": [...]}` and this unwraps the `findings` key.
    Otherwise stdout is free text: the envelope the prompt asks for is taken when it is
    there, and a bare JSON array -- what a model that ignores the shape, or the reformat
    retry, returns -- is still accepted.
    """
    if not structured:
        match extract_json_payload(stdout, kind="object"):
            case ClientSuccess(data=payload) if isinstance(payload, dict) and isinstance(
                payload.get("findings"), list
            ):
                return ClientSuccess(data=payload["findings"])
        return extract_json_payload(stdout, kind="array")
    match extract_json_payload(stdout, kind="object"):
        case ClientSuccess(data=payload) if isinstance(payload, dict) and "findings" in payload:
            return ClientSuccess(data=payload["findings"])
        case ClientSuccess():
            return ClientError(
                error_message="Structured response missing 'findings' field",
                error_code="MISSING_FINDINGS_FIELD",
                log_level="warning",
            )
        case error:
            return error


def batch_scope_paths(batch: FocusContextBatch) -> set[str]:
    """Every path this batch was entitled to make a finding about.

    Three sources, and they are not the same thing:

    - `files_context`: what was put in front of the model.
    - the `for_path` half of each related-context key (stored as "<request type>:<path>").
      The related CONTENT comes from an unlabelled sibling — `__init__.py`,
      `protocols.py`, a `base_*` file — whose own path is recorded nowhere, so a finding
      naming that sibling is the model inferring a path rather than reading one.
    - the paths of the triage's suspicions. These files are NOT in `files_context` — the
      session was asked to open them in the working tree and settle a question about
      them — so without this the scope check drops every finding the triage's work leads
      to, and the whole first pass is thrown away. The entitlement is explicit and
      narrow: someone looked at that file's diff and asked about it by name.
    """
    paths = set(batch.files_context)
    for key in batch.related_files:
        _, _, for_path = key.partition(":")
        if for_path:
            paths.add(normalize_finding_path(for_path))
    for item in batch.triage_suspicions:
        suspicion_path = (item.get("path") or "").strip()
        if suspicion_path:
            paths.add(normalize_finding_path(suspicion_path))
    return {normalize_finding_path(path) for path in paths}


def normalize_finding_path(path: str) -> str:
    """Canonicalise a path for comparison without being clever about it.

    Only the two differences a model plausibly introduces on its own: Windows
    separators and a "./" prefix. Case is preserved, because paths are case-sensitive
    where this runs and folding it would let two real files collide.
    """
    normalized = (path or "").strip().replace("\\", "/")
    while normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized


def partition_findings_by_batch_scope(
    raw_findings: list,
    batch_paths: set[str],
    manifest_paths: set[str],
    is_repo_file: Optional[Callable[[str], bool]] = None,
) -> tuple[list, list[dict]]:
    """Split a batch's findings into those it was entitled to make, and the rest.

    A findings batch is only shown a few files, but the anchoring layer can resolve a
    line in ANY file of the PR — so a finding whose path the batch never sent will
    still anchor and publish, on a file the model did not read. That is the failure
    this guards: with one or two files per batch a wrong path is unlikely, but a packed
    batch showing ten or fifteen makes misattribution an ordinary mistake.

    Two reasons to reject, kept apart because they mean different things:

    - `unknown_path`: not in this batch and not anywhere in the PR. Nothing can
      legitimately anchor it; it is a hallucinated or mangled path.
    - `outside_batch`: a real file of the PR that this batch was not shown. The
      dangerous one, precisely because it CAN anchor.

    One path outside the PR is KEPT: a file that exists in the repository
    (`is_repo_file`). The deep session reads the working tree, and what it finds there
    is the damage a PR does beyond its own diff -- on ragnarok PR #3688 the one blocking
    defect was RouterLoginScreen.kt, untouched by the PR and broken by its new shared
    password rule, and this filter threw it away as a hallucination. It cannot anchor
    inline (the file has no hunks), so it publishes in the review body. A path that is
    not a real file is still `unknown_path`.

    A path that differs from a batch path only by separator or "./" prefix is accepted
    and rewritten to the batch's spelling, so a correct finding is never lost to
    formatting. Findings with no path at all are kept: a general observation is not
    misattributed to anything, and the publish layer already handles a pathless
    finding.

    Returns `(kept, rejected)`, where each rejected entry is
    `{"path", "reason", "title"}` — enough for a log line and a count, without
    carrying the whole finding into telemetry.
    """
    if not raw_findings:
        return [], []

    canonical = {normalize_finding_path(path): path for path in batch_paths}
    manifest = {normalize_finding_path(path) for path in manifest_paths}

    kept: list = []
    rejected: list[dict] = []
    for finding in raw_findings:
        path = _finding_path(finding)
        if not path:
            kept.append(finding)
            continue

        normalized = normalize_finding_path(path)
        if normalized in canonical:
            kept.append(_with_path(finding, canonical[normalized]))
            continue

        if normalized not in manifest and is_repo_file is not None and is_repo_file(normalized):
            kept.append(_with_path(finding, normalized))
            continue

        rejected.append({
            "path": path,
            "reason": "outside_batch" if normalized in manifest else "unknown_path",
            "title": _finding_title(finding),
        })

    return kept, rejected


def _finding_path(finding: Any) -> str:
    """Read the path off a raw finding, which is a dict before normalization."""
    if isinstance(finding, dict):
        value = finding.get("path")
    else:
        value = getattr(finding, "path", None)
    return value.strip() if isinstance(value, str) else ""


def _finding_title(finding: Any) -> str:
    if isinstance(finding, dict):
        value = finding.get("title")
    else:
        value = getattr(finding, "title", None)
    return _short_title(value) if isinstance(value, str) else ""


def _with_path(finding: Any, path: str) -> Any:
    """Return the finding carrying the batch's own spelling of its path."""
    if isinstance(finding, dict):
        if finding.get("path") == path:
            return finding
        return {**finding, "path": path}
    return finding


def build_default_findings() -> list[Finding]:
    return []


TIMEOUT_FALLBACK_BATCH_SUFFIX = "_retry"


def build_timeout_fallback_batch(
    batch,
    diff: str,
    diff_manager=None,
):
    """Rebuild a timed-out worktree_reference batch in bounded hunks_only mode.

    A worktree_reference batch sends a small prompt and lets the CLI explore the
    file in the worktree — on very large files that exploration can eat the whole
    timeout and the file ends up with ZERO review. The fallback trades depth for a
    guaranteed bounded review: same files, inline diff hunks only, no exploration.
    Checklist, comment context, PR manifest and related files carry over from the
    original batch. Returns None when no path has diff hunks (nothing bounded to
    retry with).
    """
    from ..models.review_enums import FileReadMode
    from ..models.review_models import FileContextEntry, FocusContextBatch
    from .context_resolution_operations import extract_hunks_only

    files_context: dict[str, FileContextEntry] = {}
    for path in batch.files_context:
        hunks = extract_hunks_only(diff, path, diff_manager=diff_manager)
        if not hunks:
            continue
        files_context[path] = FileContextEntry(
            path=path,
            read_mode=FileReadMode.HUNKS_ONLY,
            hunks=hunks,
            approximate_chars=sum(len(hunk) for hunk in hunks),
        )

    if not files_context:
        return None

    return FocusContextBatch(
        batch_id=f"{batch.batch_id}{TIMEOUT_FALLBACK_BATCH_SUFFIX}",
        files_context=files_context,
        checklist_applicable=batch.checklist_applicable,
        comment_context=batch.comment_context,
        related_files=batch.related_files,
        pr_manifest=batch.pr_manifest,
    )


def summarize_findings_prompt_parts(parts: dict[str, str]) -> dict[str, Any]:
    """Return character counts for each prompt block."""
    return {
        "pr_context_chars": len(parts["pr_context"]),
        "comment_context_chars": len(parts["comments"]),
        "review_axes_chars": len(parts["review_axes"]),
        "files_context_chars": len(parts["files_context"]),
        "related_context_chars": len(parts["related_context"]),
        "instructions_chars": len(parts["instructions"]),
        "schema_chars": len(parts["schema"]),
    }


def _short_title(title: str, limit: int = 90) -> str:
    return title if len(title) <= limit else title[: limit - 3] + "..."
