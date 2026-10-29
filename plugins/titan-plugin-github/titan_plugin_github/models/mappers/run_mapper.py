"""Mapper from GitHub Actions runs to the view model the pane lists."""
import re
from datetime import datetime
from typing import Optional

from ..formatting import format_duration, format_relative
from ..network.rest import NetworkWorkflowRun
from ..view import UIWorkflowRun

# The branch GitHub gives a merge queue entry's run: gh-readonly-queue/<base>/pr-<number>-<sha>
_QUEUE_BRANCH = re.compile(r"^gh-readonly-queue/.+/pr-(\d+)-[0-9a-f]+$")

_STATES = {
    "success": ("success", "passed"),
    "failure": ("failure", "failed"),
    "timed_out": ("failure", "timed out"),
    "startup_failure": ("failure", "failed to start"),
    "action_required": ("failure", "action required"),
    "cancelled": ("cancelled", "cancelled"),
    "skipped": ("other", "skipped"),
    "neutral": ("other", "neutral"),
    "stale": ("other", "stale"),
}


def _seconds_between(start: str, end: str) -> Optional[float]:
    try:
        return (datetime.fromisoformat(end.replace("Z", "+00:00")) - datetime.fromisoformat(start.replace("Z", "+00:00"))).total_seconds()
    except ValueError:
        return None


def from_rest_workflow_run(run: NetworkWorkflowRun) -> UIWorkflowRun:
    """A run with its state, age and duration formatted for display."""
    if run.status != "completed":
        state, label = "running", "queued" if run.status in ("queued", "waiting", "pending") else "in progress"
    else:
        state, label = _STATES.get((run.conclusion or "").lower(), ("other", run.conclusion or "finished"))
    queue = _QUEUE_BRANCH.match(run.head_branch)
    started = run.run_started_at or run.created_at
    return UIWorkflowRun(
        id=run.id,
        title=run.display_title or run.name,
        workflow=run.name,
        event=run.event,
        state=state,
        state_label=label,
        branch=run.head_branch,
        url=run.html_url,
        pr_number=int(queue.group(1)) if queue else None,
        is_merge_queue=run.event == "merge_group",
        age=format_relative(run.created_at),
        duration=format_duration(_seconds_between(started, run.updated_at)) if state != "running" else "",
        actor=run.actor_login,
        number=run.run_number,
    )
