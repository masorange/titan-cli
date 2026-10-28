"""Merging one of your own PRs from the pane: when it may, and what the button says."""
from typing import List


def blockers(pr, unresolved: int = 0) -> List[str]:
    """Why this PR cannot be merged yet; empty when it can.

    `unresolved` is how many review conversations are still open: a branch rule can demand
    them all resolved. A review decision GitHub leaves empty (a repo whose rules do not make
    GitHub work it out) says nothing against the merge, so only a decision that is asked for
    and not given counts as "not approved".
    """
    reasons = []
    if pr.is_draft:
        reasons.append("still a draft")
    if pr.has_conflicts:
        reasons.append("has conflicts")
    if pr.review_status_summary == "changes requested":
        reasons.append("changes requested")
    elif pr.review_status_summary == "review required":
        reasons.append("not approved")
    if unresolved:
        reasons.append(f"{unresolved} unresolved conversation{'s' if unresolved != 1 else ''}")
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
