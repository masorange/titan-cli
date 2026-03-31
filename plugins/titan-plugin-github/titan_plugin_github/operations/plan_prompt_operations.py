"""
Operations for building AI prompts for review planning.

Pure functions — no UI, no side effects. All prompt templates
and fallback heuristics are defined here for independent testing.
"""

import json
from typing import Optional

from ..models.review_enums import ChecklistCategory
from ..models.review_models import (
    ChangeManifest,
    ExistingCommentIndexEntry,
    FileReviewPlan,
    ReviewChecklistItem,
    ReviewPlan,
)


# ── Prompt building ───────────────────────────────────────────────────────────


def build_review_plan_prompt(
    manifest: ChangeManifest,
    comments_index: list[ExistingCommentIndexEntry],
    checklist: list[ReviewChecklistItem],
) -> str:
    """
    Build the prompt for the first AI call: decide what to read.

    The prompt is CLI-agnostic. The instruction to use available project
    skills is included as a generic hint — each CLI knows where its own
    skills/guidelines live (Claude Code reads .claude/, Gemini uses
    GEMINI.md, Codex uses AGENTS.md).

    Args:
        manifest: Cheap PR context (files, stats, metadata)
        comments_index: Existing comments for deduplication awareness
        checklist: Full review checklist offered to AI

    Returns:
        Formatted prompt string ready to send to a headless CLI adapter
    """
    manifest_json = _manifest_to_json(manifest)
    checklist_json = _checklist_to_json(checklist)
    comments_json = _comments_to_json(comments_index)

    schema = _review_plan_schema()

    return f"""You are performing the first pass of a two-phase code review for a pull request.

Your task: analyze the PR metadata and decide WHICH files deserve careful reading and WHICH review categories apply. You are NOT reviewing the code yet — only planning the review.

## PR Manifest
{manifest_json}

## Review Checklist (select which apply)
{checklist_json}

## Existing Comments (avoid duplicates in your suggestions later)
{comments_json}

## Project Skills
Use any project-specific skills, guidelines, or tools available in your context if they're relevant to this analysis.

## Instructions

Respond ONLY with valid JSON matching this exact schema:
{schema}

Rules for applicable_checklist:
- Select ONLY categories relevant to what this PR actually changes
- Do not select categories that don't apply (e.g. no "security" for a pure docs PR)

Rules for file_plan:
- Cover every changed file listed in the manifest
- Use "hunks_only" for simple/mechanical changes
- Use "expanded_hunks" for complex logic changes (needs surrounding context)
- Use "full_file" ONLY for new files under 300 lines or critical parsers/adapters
- Assign priority based on how likely this file has bugs worth catching

Rules for extra_context_requests:
- Maximum 3 requests
- Only request if you genuinely need it to evaluate correctness
- Use "related_tests" for the test file of a module
- Use "related_context" for a dependency/parent module

Return ONLY the JSON object. No explanation, no markdown fences."""


def _manifest_to_json(manifest: ChangeManifest) -> str:
    data = {
        "pr": {
            "number": manifest.pr.number,
            "title": manifest.pr.title,
            "author": manifest.pr.author,
            "base": manifest.pr.base,
            "head": manifest.pr.head,
            "description": manifest.pr.description[:500] if manifest.pr.description else "",
        },
        "total_additions": manifest.total_additions,
        "total_deletions": manifest.total_deletions,
        "files": [
            {
                "path": f.path,
                "status": f.status,
                "additions": f.additions,
                "deletions": f.deletions,
                "is_test": f.is_test,
            }
            for f in manifest.files
        ],
    }
    return json.dumps(data, indent=2)


def _checklist_to_json(checklist: list[ReviewChecklistItem]) -> str:
    data = [
        {
            "id": item.id,
            "name": item.name,
            "description": item.description,
        }
        for item in checklist
    ]
    return json.dumps(data, indent=2)


def _comments_to_json(comments: list[ExistingCommentIndexEntry]) -> str:
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


def _review_plan_schema() -> str:
    return json.dumps(
        {
            "applicable_checklist": ["<checklist_id>", "..."],
            "file_plan": [
                {
                    "path": "<file_path>",
                    "priority": "<high|medium|low>",
                    "read_mode": "<hunks_only|expanded_hunks|full_file>",
                    "reasons": ["<why this priority and mode>"],
                }
            ],
            "extra_context_requests": [
                {
                    "type": "<related_tests|related_context>",
                    "for_path": "<which file this supports>",
                    "reason": "<why needed>",
                }
            ],
        },
        indent=2,
    )


# ── Fallback heuristic ────────────────────────────────────────────────────────


def build_default_review_plan(
    manifest: ChangeManifest,
    checklist: Optional[list[ReviewChecklistItem]] = None,
) -> ReviewPlan:
    """
    Build a conservative ReviewPlan without AI.

    Used as fallback when the AI call fails or produces unparseable output.
    Heuristics:
    - New files < 300 lines → full_file
    - Large changes (>50 lines) → expanded_hunks, high priority
    - Small changes → hunks_only, medium or low priority
    - Test files → low priority
    - All checklist items apply by default (conservative)

    Args:
        manifest: PR change manifest
        checklist: Review checklist (if None, all categories apply)

    Returns:
        Conservative ReviewPlan that covers everything
    """
    file_plans: list[FileReviewPlan] = []

    for f in manifest.files:
        total_changes = f.additions + f.deletions

        if f.is_test:
            priority = "low"
            read_mode = "hunks_only"
        elif f.status == "added" and f.size_lines < 300:
            priority = "high"
            read_mode = "full_file"
        elif total_changes > 50:
            priority = "high"
            read_mode = "expanded_hunks"
        elif total_changes > 10:
            priority = "medium"
            read_mode = "hunks_only"
        else:
            priority = "low"
            read_mode = "hunks_only"

        file_plans.append(
            FileReviewPlan(
                path=f.path,
                priority=priority,
                read_mode=read_mode,
                reasons=["Fallback heuristic: AI plan parsing failed"],
            )
        )

    # Default: all checklist categories apply
    if checklist:
        applicable = [item.id for item in checklist]
    else:
        applicable = list(ChecklistCategory)

    return ReviewPlan(
        applicable_checklist=applicable,
        file_plan=file_plans,
        extra_context_requests=[],
    )
