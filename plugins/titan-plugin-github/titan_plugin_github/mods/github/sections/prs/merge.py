"""Merging one of your own PRs from the pane: when it may, and what the button says."""
from typing import List


def blockers(pr) -> List[str]:
    """Why this PR cannot be merged yet; empty when it can."""
    reasons = []
    if pr.is_draft:
        reasons.append("still a draft")
    if pr.has_conflicts:
        reasons.append("has conflicts")
    if pr.review_status_summary != "approved":
        reasons.append("changes requested" if pr.review_status_summary == "changes requested" else "not approved")
    if pr.checks_state == "failing":
        reasons.append("checks failing")
    elif pr.checks_state == "running":
        reasons.append("checks running")
    return reasons


def uses_queue(pr, queue) -> bool:
    """Whether merging this PR means joining the merge queue of the branch it lands on."""
    return bool(queue is not None and queue.configured and queue.branch == pr.base_ref)


def label(pr, queue) -> str:
    return "⇉ Add to queue" if uses_queue(pr, queue) else "⇉ Squash & merge"
