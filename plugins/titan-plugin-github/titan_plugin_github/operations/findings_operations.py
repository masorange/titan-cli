"""
Operations for building AI prompts for targeted code review (second IA call).

Pure functions — no UI, no side effects. Prompt templates and helpers for
the findings phase: ReviewContextPackage → Finding[].
"""

import json

from ..models.review_models import (
    ExistingCommentIndexEntry,
    FileContextEntry,
    Finding,
    ReviewChecklistItem,
    ReviewContextPackage,
)


# ── Prompt building ───────────────────────────────────────────────────────────


def build_review_findings_prompt(package: ReviewContextPackage) -> str:
    """
    Build the prompt for the second AI call: find actionable problems.

    The AI receives exact code context (not just metadata) and is asked to
    produce a JSON array of Finding objects. Each finding represents a real,
    actionable problem — not style preferences or nitpicks unless clearly wrong.

    The prompt is CLI-agnostic. Project skills hint included generically.

    Args:
        package: Complete context package from resolve_review_context step

    Returns:
        Formatted prompt string ready to send to a headless CLI adapter
    """
    checklist_json = _checklist_to_json(package.checklist_applicable)
    existing_json = _existing_comments_to_json(package.existing_comments_compact)
    files_text = _files_context_to_text(package.files_context)
    related_text = _related_files_to_text(package.related_files)
    schema = _finding_schema()
    pr_context = _pr_context_to_text(package)

    return f"""You are performing the second pass of a two-phase code review.

The first pass already decided WHAT to read. Now your task is to read the exact code provided and find ACTIONABLE problems.

## PR Context
{pr_context}

## Code to Review
{files_text}{related_text}

## Review Checklist (applicable to this PR)
{checklist_json}

## Existing Comments (do NOT duplicate these)
{existing_json}

## Project Skills
Use any project-specific skills, guidelines, or tools available in your context if they're relevant to this review.

## Instructions

Find problems in the code above. For each problem, produce one Finding JSON object.

Rules:
- Only report ACTIONABLE problems (bugs, missing error handling, incorrect logic, security issues)
- Do NOT report style preferences unless they indicate a real bug
- Do NOT duplicate existing comments (listed above)
- Severity: "blocking" = will cause bugs/failures, "important" = should be fixed, "nit" = minor improvement
- `suggested_comment` must be a ready-to-post GitHub review comment (include the evidence and why)
- If there are no findings, return an empty array: []

Respond ONLY with a valid JSON array matching this exact schema for each element:
{schema}

Return ONLY the JSON array. No explanation, no markdown fences."""


def _pr_context_to_text(package: ReviewContextPackage) -> str:
    if not package.pr_manifest:
        return "No PR metadata available."
    pr = package.pr_manifest
    return (
        f"PR #{pr.number}: {pr.title}\n"
        f"Author: {pr.author} | Base: {pr.base} → Head: {pr.head}\n"
        f"Description: {pr.description[:300] if pr.description else '(none)'}"
    )


def _checklist_to_json(checklist: list[ReviewChecklistItem]) -> str:
    if not checklist:
        return "[]"
    data = [
        {
            "id": item.id,
            "name": item.name,
            "description": item.description,
        }
        for item in checklist
    ]
    return json.dumps(data, indent=2)


def _existing_comments_to_json(comments: list[ExistingCommentIndexEntry]) -> str:
    if not comments:
        return "[]"
    data = [
        {
            "path": c.path,
            "line": c.line,
            "category": c.category,
            "title": c.title,
            "is_resolved": c.is_resolved,
        }
        for c in comments
    ]
    return json.dumps(data, indent=2)


def _files_context_to_text(files_context: dict[str, FileContextEntry]) -> str:
    if not files_context:
        return "(no files to review)\n"

    parts: list[str] = []
    for path, entry in files_context.items():
        parts.append(f"### {path}")

        if entry.full_content:
            parts.append("```")
            parts.append(entry.full_content)
            parts.append("```")
        elif entry.expanded_hunks:
            for hunk in entry.expanded_hunks:
                parts.append("```diff")
                parts.append(hunk)
                parts.append("```")
        elif entry.hunks:
            for hunk in entry.hunks:
                parts.append("```diff")
                parts.append(hunk)
                parts.append("```")
        else:
            parts.append("(no content available)")

        parts.append("")

    return "\n".join(parts)


def _related_files_to_text(related_files: dict[str, str]) -> str:
    if not related_files:
        return ""

    parts: list[str] = ["\n## Related Files (for context only — not primary review targets)"]
    for label, content in related_files.items():
        parts.append(f"\n### {label}")
        parts.append("```")
        parts.append(content[:2000])  # Cap related files to avoid token explosion
        parts.append("```")
    return "\n".join(parts) + "\n"


def _finding_schema() -> str:
    return json.dumps(
        [
            {
                "severity": "<blocking|important|nit>",
                "category": "<problem category, e.g. error_handling>",
                "path": "<file path>",
                "line": "<line number or null for file-level>",
                "title": "<short, actionable problem description>",
                "why": "<explanation of why this is a problem>",
                "evidence": "<code snippet or specific reference>",
                "suggested_comment": "<ready-to-post GitHub review comment>",
            }
        ],
        indent=2,
    )


# ── Fallback ──────────────────────────────────────────────────────────────────


def build_default_findings() -> list[Finding]:
    """
    Return an empty findings list as fallback when AI call fails.

    Used when the AI call fails or produces unparseable output.
    Returning empty rather than fabricating findings is always safer.

    Returns:
        Empty list (no findings is a valid state)
    """
    return []
