"""Operations for building AI prompts for focused findings review."""

import json

from ..models.review_models import CommentContextEntry, Finding, FocusContextBatch, ReviewChecklistItem


def build_review_findings_prompt(batch: FocusContextBatch) -> str:
    checklist_json = _checklist_to_json(batch.checklist_applicable)
    comments_json = _comments_to_json(batch.comment_context)
    files_text = _files_context_to_text(batch.files_context)
    related_text = _related_files_to_text(batch.related_files)
    pr_context = _pr_context_to_text(batch)
    schema = _finding_schema()

    return f"""You are performing a focused pull request code review.

This is one bounded review batch. Review only the provided code and report actionable problems that are actually present.

## PR Context
{pr_context}

## Existing Comments (do not duplicate these)
{comments_json}

## Review Axes
{checklist_json}

## Code to Review
{files_text}{related_text}

## Instructions
- Only report actionable issues: correctness, error handling, security, validation, API, concurrency, or missing regression coverage when clearly required
- Do not repeat issues already covered by Existing Comments
- Do not report deleted lines as findings
- Do not speculate beyond the shown code
- Do not claim that a function, overload, or parameter does not exist unless the relevant declaration is clearly visible in the provided context
- Prefer describing an observable behavior risk over making an unverified compilation claim
- Include a short `snippet` copied from the exact added/context line that should anchor the comment; use null only if no stable inline anchor exists
- If the repository exposes project instructions, skills, or review documentation in the current working tree, use them when relevant, but do not depend on them
- If there are no findings, return []

Respond ONLY with a valid JSON array matching this schema:
{schema}
"""


def _pr_context_to_text(batch: FocusContextBatch) -> str:
    if not batch.pr_manifest:
        return f"Batch {batch.batch_id}"
    pr = batch.pr_manifest
    return (
        f"PR #{pr.number}: {pr.title}\n"
        f"Base {pr.base} -> Head {pr.head}\n"
        f"Batch: {batch.batch_id} | Approx chars: {batch.approximate_chars}"
    )


def _checklist_to_json(checklist: list[ReviewChecklistItem]) -> str:
    return json.dumps(
        [
            {"id": item.id, "name": item.name, "description": item.description}
            for item in checklist
        ],
        indent=2,
    )


def _comments_to_json(comments: list[CommentContextEntry]) -> str:
    return json.dumps(
        [
            {
                "kind": entry.kind,
                "path": entry.path,
                "line": entry.line,
                "category": entry.category,
                "title": entry.title,
                "summary": entry.summary,
                "is_resolved": entry.is_resolved,
            }
            for entry in comments
        ],
        indent=2,
    )


def _files_context_to_text(files_context: dict) -> str:
    if not files_context:
        return "(no files to review)\n"

    parts: list[str] = []
    for path, entry in files_context.items():
        parts.append(f"### {path}")
        if entry.full_content:
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
        parts.extend([f"\n### {label}", "```", content[:2000], "```"])
    return "\n".join(parts) + "\n"


def _add_line_numbers(content: str) -> str:
    lines = content.splitlines()
    width = len(str(len(lines)))
    return "\n".join(f"{str(i + 1).rjust(width)} | {line}" for i, line in enumerate(lines))


def _annotate_diff_hunk(hunk: str) -> str:
    import re

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

    result = [header_line] if header_line else []
    current_line = new_line_start
    width = len(str(current_line + 100))

    for line in lines:
        if line.startswith("@@"):
            continue
        if line.startswith("---") or line.startswith("+++"):
            result.append(line)
        elif line.startswith("-"):
            result.append(f"[DELETED - do not review] {line[1:]}")
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
    return json.dumps(
        [
            {
                "severity": "<blocking|important|nit>",
                "category": "<problem category>",
                "path": "<file path>",
                "line": "<line or null>",
                "title": "<short actionable title>",
                "why": "<why this is a problem>",
                "evidence": "<exact supporting snippet>",
                "snippet": "<short anchor snippet from the target line or null>",
                "suggested_comment": "<ready-to-post GitHub review comment>",
            }
        ],
        indent=2,
    )


def build_default_findings() -> list[Finding]:
    return []
