"""Review requests and the user's own PRs, through the github plugin client."""
from typing import List, Optional

from titan_cli.core.result import ClientError, ClientSuccess

from ...models import Others, Prs


def read_prs(github) -> Prs:
    if github is None:
        return Prs(error="github plugin not available")
    repo = github.get_repo_full_name()
    results = []
    for result in (github.list_pending_review_prs(), github.list_my_prs(), github.count_open_prs()):
        match result:
            case ClientSuccess(data=data):
                results.append(data)
            case ClientError(error_message=err):
                return Prs(repo=repo, error=err)
    to_review, mine, open_count = results
    return Prs(repo=repo, to_review=to_review, mine=mine, open_count=open_count)


def read_others(github) -> Others:
    """Every open PR, in a read of its own (the longest one, so it never blocks the other lists)."""
    if github is None:
        return Others(error="github plugin not available")
    match github.list_all_prs():
        case ClientSuccess(data=data):
            return Others(prs=data)
        case ClientError(error_message=err):
            return Others(error=err)


def new_review_requests(before: Optional[Prs], after: Prs) -> List[int]:
    """Review requests that arrived since the last good poll, not the ones there at start."""
    if before is None or before.error is not None or after.error is not None:
        return []
    known = {p.number for p in before.to_review}
    return [p.number for p in after.to_review if p.number not in known]
