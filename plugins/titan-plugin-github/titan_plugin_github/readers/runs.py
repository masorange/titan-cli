"""Workflow runs: the repo's latest, and the merge queue's own, through the github plugin client."""
from dataclasses import replace
from typing import Optional

from titan_cli.core.result import ClientError, ClientSuccess

from .models import Runs

# Runs shown at first, and how many more each "show more" adds; GitHub answers at most MAX in a page.
PAGE = 10
MAX = 100


def read_runs(github, trigger: Optional[str], limit: int) -> Runs:
    """The latest `limit` runs, of one trigger event when given ("merge_group" is the merge queue's)."""
    if github is None:
        return Runs(limit=limit, error="github plugin not available")
    match github.list_workflow_runs(trigger=trigger, limit=limit):
        case ClientSuccess(data=data):
            return Runs(runs=data, limit=limit)
        case ClientError(error_message=err):
            return Runs(limit=limit, error=err)


def limit_of(m, key: str) -> int:
    """What the next read of this list asks for."""
    current: Optional[Runs] = m.state.get(key)
    return current.limit if current is not None else PAGE


def has_more(runs: Runs) -> bool:
    """Whether GitHub may hold older runs than those listed: the last read came back full."""
    return len(runs.runs) >= runs.limit and runs.limit < MAX


def show_more(m, key: str) -> None:
    """Ask for another PAGE runs and read the list again, off the UI thread."""
    current: Optional[Runs] = m.state.get(key)
    if current is None:
        return
    m.state.set(key, replace(current, limit=min(current.limit + PAGE, MAX)))
    reread = m.state.get(f"refresh_{key}")
    if reread is not None:
        m.run(reread)
