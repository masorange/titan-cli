"""What one run of Respond to PR Comments did, recorded so it can be scored later.

Scoring this workflow means answering, per comment: was it fixed, fixed but something else
broke, answered wrongly, or replied to? The first three need the COMMIT each comment produced,
and that link lived nowhere - reconstructing it for PR #276 meant reading 39 threads for the
hash Titan posts as a reply and blaming a later review's findings by hand.

So the run writes it down: one row per comment with its verdict, what the user chose, whether
they agreed with the verdict, and the commit that came out. A later review's findings then
attribute themselves - `git blame` on the finding's line gives a commit, and the record says
which comment that commit was answering.

The record goes to disk next to the material, not only to the log: logs rotate, and the run
that opened this domain was one rotation away from being gone.
"""

from typing import Any, Iterable, Optional

from ..models.review_enums import CommentVerdictType
from ..models.view import UICommentThread

RUNS_DIR = "runs"

#: What each choice in the loop means for the verdict it was shown next to. A choice that
#: changes code agrees with `apply` and contradicts the other three, and the other way round.
_CHANGES_CODE = {"ai_review", "change_manually"}
_ANSWERS_WITHOUT_CHANGING = {"use_reply", "reply", "resolve"}


def verdict_agreement(verdict_type: Optional[str], choice: Optional[str]) -> Optional[bool]:
    """Did the user go along with the verdict? None when the question does not apply.

    None covers three real cases that must not be counted as disagreement: no verdict was
    offered, the user skipped (no decision), and the user exited the run. A verdict is judged
    by what the user DID about it, not by a button labelled "accept": `skip` says nothing
    about whether the session was right.
    """
    if not verdict_type or not choice:
        return None
    if choice in _CHANGES_CODE:
        return verdict_type == CommentVerdictType.APPLY.value
    if choice in _ANSWERS_WITHOUT_CHANGING:
        return verdict_type != CommentVerdictType.APPLY.value
    return None


def build_decision_row(
    thread: UICommentThread,
    verdict: Optional[Any],
    choice: Optional[str],
    commit: Optional[str],
    replied: bool,
) -> dict:
    """One comment's row: what was proposed, what was done, and what came out of it."""
    main = thread.main_comment
    verdict_type = verdict.verdict.value if verdict else None
    return {
        "comment_id": main.id if main else None,
        "path": main.path if main else None,
        "line": main.line if main else None,
        "is_general": thread.is_general_comment,
        "author": main.author_login if main else None,
        "verdict": verdict_type,
        "verdict_reason": verdict.reason if verdict else None,
        "files_affected": list(verdict.files_affected) if verdict else [],
        "callers_to_check": list(verdict.callers_to_check) if verdict else [],
        "choice": choice,
        "agreed_with_verdict": verdict_agreement(verdict_type, choice),
        "commit": commit,
        "replied": replied,
    }


def build_run_record(
    run_id: Optional[str],
    pr_number: Optional[int],
    head_sha: Optional[str],
    judged: dict,
    decisions: Iterable[dict],
    exited_early: bool = False,
) -> dict:
    """The whole run as one document, with the counts a score is read off.

    `judged` carries what the judging step published about itself (CLI, model, cost, how many
    comments it answered); it is empty when that step did not run, which is itself a fact
    worth recording - a run with no verdicts is the baseline variant.
    """
    rows = list(decisions)
    counts: dict[str, int] = {}
    for row in rows:
        counts[row["choice"] or "none"] = counts.get(row["choice"] or "none", 0) + 1
    agreements = [row["agreed_with_verdict"] for row in rows]
    return {
        "run": run_id,
        "pr": pr_number,
        "head_sha": head_sha,
        "judgement": judged or {},
        "comments": len(rows),
        "choices": counts,
        "commits": {
            str(row["comment_id"]): row["commit"] for row in rows if row.get("commit")
        },
        "agreed": sum(1 for value in agreements if value is True),
        "overruled": sum(1 for value in agreements if value is False),
        "not_judged": sum(1 for row in rows if row["verdict"] is None),
        "exited_early": exited_early,
        "decisions": rows,
    }


def run_record_path(run_id: Optional[str]) -> str:
    """Where a run's record goes, relative to the material directory."""
    return f"{RUNS_DIR}/{run_id or 'unknown'}.json"
