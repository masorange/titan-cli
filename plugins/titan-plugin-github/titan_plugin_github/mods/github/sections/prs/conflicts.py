"""Which files of a PR clash with its base branch.

GitHub only says *that* a PR conflicts, never with what, so git answers:
`list_merge_conflicts` merges the two refs in memory, touching neither the
working tree nor HEAD, which is why this works for a branch that is not
checked out. Resolving them is the `resolve-pr-conflicts` workflow's job.
"""
from titan_cli.core.result import ClientError, ClientSuccess

from ...models import Conflicts


def of(m, number: int):
    """What is known about this PR's conflicts, if it has been asked about."""
    return (m.state.get("conflicts") or {}).get(str(number))


def start(m, pr, remote: str = "origin") -> None:
    """Ask git, unless it is already being asked; the claim is made before returning."""
    key = str(pr.number)
    claimed = []

    def claim(all_):
        all_ = all_ or {}
        if all_.get(key) is not None and all_[key].status == "running":
            return all_
        claimed.append(True)
        return {**all_, key: Conflicts("running")}

    m.state.update("conflicts", claim, default={})
    if claimed:
        m.run(lambda: read(m, pr, remote))


def read(m, pr, remote: str = "origin") -> None:
    """Runs on a background thread: git is asked, and the answer kept in state."""
    def put(value: Conflicts) -> None:
        m.state.update("conflicts", lambda all_: {**(all_ or {}), str(pr.number): value}, default={})

    git = m.client("git")
    if git is None:
        put(Conflicts("error", error="the git plugin is not enabled"))
        return
    # A stale remote-tracking ref would answer about yesterday's branch; fetching
    # only moves those refs, never the working tree.
    for branch in (pr.base_ref, pr.head_ref):
        git.fetch(remote=remote, branch=branch)
    match git.list_merge_conflicts(f"{remote}/{pr.base_ref}", f"{remote}/{pr.head_ref}"):
        case ClientSuccess(data=files):
            put(Conflicts("done", files=list(files)))
        case ClientError(error_message=err):
            put(Conflicts("error", error=err))
