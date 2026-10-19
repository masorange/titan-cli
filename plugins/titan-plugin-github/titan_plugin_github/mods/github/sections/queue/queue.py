"""The merge queue, through the github plugin client."""
from typing import List, Optional

from titan_cli.core.result import ClientError, ClientSuccess

from ...models import Queue


def read_queue(github, shown: int) -> Queue:
    if github is None:
        return Queue(error="github plugin not available")
    match github.get_merge_queue(max_entries=shown):
        case ClientSuccess(data=q):
            return Queue(configured=q.is_configured, branch=q.branch, merge_method=q.merge_method,
                         total=q.total, entries=list(q.entries))
        case ClientError(error_message=err):
            return Queue(error=err)


def left_queue(before: Optional[Queue], after: Queue) -> List[int]:
    """My PRs that were queued and no longer are: merged or kicked out, either way news."""
    if before is None or before.error is not None or after.error is not None:
        return []
    still = {e.pr_number for e in after.entries}
    return [e.pr_number for e in before.entries if e.is_mine and e.pr_number not in still]
