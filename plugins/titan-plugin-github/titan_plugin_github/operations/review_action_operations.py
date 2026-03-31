"""
Operations for building and submitting review actions.

Pure business logic for Phase 5 of the new_findings_review pipeline:
converting Finding objects into ReviewActionProposal objects and building
the GitHub API payload for submission.
"""

from typing import Dict, List, Optional

from ..models.review_models import Finding, ReviewActionProposal
from .code_review_operations import (
    extract_diff_for_file,
    extract_valid_diff_lines,
)


def build_new_comment_actions(findings: List[Finding]) -> List[ReviewActionProposal]:
    """
    Convert deduplicated findings into ReviewActionProposal objects.

    Args:
        findings: Validated, deduplicated Finding objects from Phase 4

    Returns:
        List of ReviewActionProposal with action_type='new_comment'
    """
    actions = []
    for finding in findings:
        actions.append(
            ReviewActionProposal(
                action_type="new_comment",
                source="new_finding",
                path=finding.path,
                line=finding.line,
                title=finding.title,
                body=finding.suggested_comment,
                reasoning=finding.why,
                category=finding.category,
                severity=finding.severity,
            )
        )
    return actions


def build_review_action_payload(
    actions: List[ReviewActionProposal],
    commit_sha: str,
    diff: str = "",
) -> Dict:
    """
    Build the GitHub API payload from approved ReviewActionProposal objects.

    Handles new_comment and reply_to_thread action types. Actions with
    action_type='resolve_thread' are excluded — they are handled separately
    via direct API call in the submit step.

    For new_comment actions, tries to place the comment inline if the line
    is present in the diff. Falls back to the general review body otherwise.

    Args:
        actions: Approved ReviewActionProposal objects
        commit_sha: Head commit SHA for inline comments
        diff: Full PR unified diff (used to validate inline line positions)

    Returns:
        Dict with keys: commit_id, comments (list), body (str, optional)
    """
    valid_lines = extract_valid_diff_lines(diff) if diff else {}
    inline_comments = []
    general_parts: List[str] = []

    for action in actions:
        if action.action_type == "resolve_thread":
            continue

        if action.action_type == "reply_to_thread" and action.thread_id:
            inline_comments.append({
                "body": action.body,
                "in_reply_to": int(action.thread_id),
            })
            continue

        # new_comment — try inline first, fall back to general body
        if action.path and action.line:
            file_valid_lines = valid_lines.get(action.path, set())
            if action.line in file_valid_lines:
                inline_comments.append({
                    "path": action.path,
                    "line": action.line,
                    "side": "RIGHT",
                    "body": action.body,
                })
                continue

        # Fallback: include in the general review body
        location = f"**{action.path}**" if action.path else "General"
        if action.line:
            location += f" (line {action.line})"
        general_parts.append(f"{location}:\n{action.body}")

    payload: Dict = {"commit_id": commit_sha, "comments": inline_comments}
    if general_parts:
        payload["body"] = "\n\n---\n\n".join(general_parts)

    return payload


def extract_diff_hunk_for_action(action: ReviewActionProposal, diff: str) -> Optional[str]:
    """
    Extract the diff hunk around an action's file/line for display in the UI.

    Args:
        action: The action whose code context to extract
        diff: Full PR unified diff

    Returns:
        Hunk string starting with @@, or None if not found
    """
    if not diff or not action.path or not action.line:
        return None

    from .code_review_operations import extract_hunk_for_line

    file_diff = extract_diff_for_file(diff, action.path)
    if not file_diff:
        return None

    return extract_hunk_for_line(file_diff, action.line)
