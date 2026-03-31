"""
Operations for the thread resolution pipeline (Phase 6).

Pure functions — no UI, no side effects. Takes open review threads and produces
ReviewActionProposal objects (resolve_thread / reply_to_thread) for the shared
validate → submit pipeline.
"""

import json
from typing import Optional

from ..models.review_models import (
    ReviewActionProposal,
    ThreadDecision,
    ThreadReviewCandidate,
    ThreadReviewContext,
)
from ..models.view import UICommentThread


# ── Candidate selection ───────────────────────────────────────────────────────


def build_thread_review_candidates(
    threads: list[UICommentThread],
) -> list[ThreadReviewCandidate]:
    """
    Filter threads worth AI analysis from the full list of open PR threads.

    Includes only inline (non-general) unresolved threads — general comments
    (thread_id starts with 'general_') cannot be resolved via GraphQL and
    are excluded.

    Args:
        threads: All unresolved inline review threads from fetch_pr_review_bundle

    Returns:
        ThreadReviewCandidate list ready for context enrichment
    """
    candidates = []
    for thread in threads:
        if thread.is_general_comment:
            continue
        if thread.is_resolved:
            continue

        main = thread.main_comment
        replies = thread.replies

        last_reply_author = replies[-1].author_login if replies else None
        last_reply_body = replies[-1].body if replies else None

        candidates.append(
            ThreadReviewCandidate(
                thread_id=thread.thread_id,
                path=main.path,
                line=main.line,
                main_comment_body=main.body,
                main_comment_author=main.author_login,
                replies_count=len(replies),
                last_reply_author=last_reply_author,
                last_reply_body=last_reply_body,
                is_outdated=thread.is_outdated,
            )
        )

    return candidates


# ── Context enrichment ────────────────────────────────────────────────────────


def build_thread_review_contexts(
    candidates: list[ThreadReviewCandidate],
    threads: list[UICommentThread],
    diff: str,
) -> list[ThreadReviewContext]:
    """
    Enrich each candidate with diff hunk context and full reply history.

    Args:
        candidates: Selected threads from build_thread_review_candidates
        threads: Original UICommentThread list (for extracting all replies)
        diff: Full PR unified diff

    Returns:
        ThreadReviewContext list ready for AI prompt building
    """
    thread_map = {t.thread_id: t for t in threads}
    contexts = []

    for candidate in candidates:
        thread = thread_map.get(candidate.thread_id)
        all_replies: list[dict] = []
        if thread:
            for reply in thread.replies:
                all_replies.append({"author": reply.author_login, "body": reply.body})

        hunk = None
        if candidate.path and candidate.line:
            hunk = _extract_hunk_near_line(diff, candidate.path, candidate.line)

        contexts.append(
            ThreadReviewContext(
                thread_id=candidate.thread_id,
                path=candidate.path,
                line=candidate.line,
                main_comment_body=candidate.main_comment_body,
                main_comment_author=candidate.main_comment_author,
                all_replies=all_replies,
                current_code_hunk=hunk,
                is_outdated=candidate.is_outdated,
            )
        )

    return contexts


def _extract_hunk_near_line(diff: str, path: str, line: int, context: int = 5) -> Optional[str]:
    """
    Extract lines from the diff near `line` for the given file path.

    Args:
        diff: Full PR unified diff
        path: File path as it appears in the diff header
        line: Target line number
        context: Number of lines before/after to include

    Returns:
        Extracted diff hunk string, or None if the file/line is not in the diff
    """
    from .code_review_operations import extract_diff_for_file, extract_hunk_for_line

    file_diff = extract_diff_for_file(diff, path)
    if not file_diff:
        return None
    return extract_hunk_for_line(file_diff, line)


# ── Prompt building ───────────────────────────────────────────────────────────


def build_thread_resolution_prompt(contexts: list[ThreadReviewContext]) -> str:
    """
    Build the prompt for the thread resolution AI call.

    Presents each open thread with its full conversation and current code hunk.
    Asks the AI to decide whether the author's response resolves the issue,
    needs a follow-up reply, or can be skipped.

    Args:
        contexts: Enriched thread contexts from build_thread_review_contexts

    Returns:
        Formatted prompt string ready to send to a headless CLI adapter
    """
    threads_text = _threads_to_text(contexts)
    schema = _thread_decision_schema()

    return f"""You are reviewing open PR comment threads to decide how to proceed with each one.

For each thread, you have:
- The original reviewer comment
- All replies from the PR author and other reviewers
- The current state of the code near the commented line (if available)

## Open Threads

{threads_text}

## Your Task

For each thread, decide one of the following actions:

- **resolved**: The author's changes or replies have fully addressed the issue. The thread can be marked as resolved.
- **insist**: The issue still exists in the code. The reply did not fix it. Post a follow-up comment insisting on the fix.
- **reply**: The concern is valid but needs clarification, reformulation, or acknowledgment. Post a reply.
- **skip**: The thread is not actionable now (e.g., out of scope, already agreed to fix later, administrative).

Rules:
- Base your decision on the **current code** shown, not assumptions
- If the code hunk shows the fix was applied, prefer "resolved"
- If no code hunk is available and the author replied affirmatively, lean toward "resolved"
- "insist" is for cases where the problem clearly persists in code
- "reply" is for nuanced situations requiring clarification
- "skip" only when the thread is clearly not actionable
- `suggested_reply` is REQUIRED when decision is "insist" or "reply". It must be a complete, ready-to-post reply.
- `suggested_reply` must be null when decision is "resolved" or "skip"

Respond ONLY with a valid JSON array matching this exact schema for each element:
{schema}

Return ONLY the JSON array. No explanation, no markdown fences."""


def _threads_to_text(contexts: list[ThreadReviewContext]) -> str:
    if not contexts:
        return "(no threads to review)"

    parts: list[str] = []
    for i, ctx in enumerate(contexts, 1):
        location = f"`{ctx.path}` line {ctx.line}" if ctx.path else "general"
        if ctx.is_outdated:
            location += " *(outdated — code may have moved)*"

        parts.append(f"### Thread {i} [thread_id: {ctx.thread_id}]")
        parts.append(f"**Location**: {location}")
        parts.append(f"**Original comment** by @{ctx.main_comment_author}:")
        parts.append(f"> {ctx.main_comment_body}")

        if ctx.all_replies:
            parts.append(f"\n**Replies** ({len(ctx.all_replies)}):")
            for reply in ctx.all_replies:
                parts.append(f"- @{reply['author']}: {reply['body']}")
        else:
            parts.append("\n*(no replies yet)*")

        if ctx.current_code_hunk:
            parts.append("\n**Current code near this line:**")
            parts.append("```diff")
            parts.append(ctx.current_code_hunk)
            parts.append("```")
        else:
            parts.append("\n*(code context not available — file may be deleted or line not in diff)*")

        parts.append("")

    return "\n".join(parts)


def _thread_decision_schema() -> str:
    return json.dumps(
        [
            {
                "thread_id": "<thread_id exactly as shown in the Thread header>",
                "decision": "<resolved|insist|reply|skip>",
                "reasoning": "<why this decision was made>",
                "suggested_reply": "<complete reply text, or null>",
                "category": "<issue category, e.g. error_handling, or null>",
                "severity": "<important|nit|none>",
            }
        ],
        indent=2,
    )


# ── Action building ───────────────────────────────────────────────────────────


def build_thread_actions(
    decisions: list[ThreadDecision],
) -> list[ReviewActionProposal]:
    """
    Transform ThreadDecision objects into ReviewActionProposal objects.

    Maps decisions to action types:
    - resolved → resolve_thread
    - insist / reply → reply_to_thread (with suggested_reply as body)
    - skip → (excluded, no action created)

    Args:
        decisions: Validated ThreadDecision objects from normalize_thread_decisions

    Returns:
        List of ReviewActionProposal with source='thread_followup'
    """
    actions = []
    for decision in decisions:
        if decision.decision == "skip":
            continue

        if decision.decision == "resolved":
            actions.append(
                ReviewActionProposal(
                    action_type="resolve_thread",
                    source="thread_followup",
                    thread_id=decision.thread_id,
                    title="Resolve thread (issue addressed)",
                    body="",
                    reasoning=decision.reasoning,
                    category=decision.category,
                    severity=decision.severity if decision.severity != "none" else None,
                )
            )
        elif decision.decision in ("insist", "reply"):
            reply_body = decision.suggested_reply or decision.reasoning
            label = "Insist" if decision.decision == "insist" else "Reply"
            actions.append(
                ReviewActionProposal(
                    action_type="reply_to_thread",
                    source="thread_followup",
                    thread_id=decision.thread_id,
                    title=f"{label}: {decision.category or 'follow-up'}",
                    body=reply_body,
                    reasoning=decision.reasoning,
                    category=decision.category,
                    severity=decision.severity if decision.severity != "none" else None,
                )
            )

    return actions
