"""Review conversations left unresolved on a PR: a branch rule can refuse the merge for them.

GitHub's review decision says nothing about them, so the PR is asked once its row
is opened, and again with each read of the lists while it stays open.
"""
from titan_cli.core.result import ClientError, ClientSuccess

from titan_plugin_github.readers.models import Threads


def of(m, number: int):
    """What is known about this PR's open conversations, if it has been asked about."""
    return (m.state.get("threads") or {}).get(str(number))


def unresolved(m, number: int) -> int:
    """How many are open; none while unknown, since GitHub refuses a merge that cannot go through."""
    found = of(m, number)
    return found.unresolved if found is not None and found.status == "done" else 0


def start(m, number: int) -> None:
    """Ask GitHub, unless it is already being asked; the claim is made before returning."""
    key = str(number)
    claimed = []

    def claim(all_):
        all_ = all_ or {}
        current = all_.get(key)
        if current is not None and current.status == "running":
            return all_
        # A count already known stays on screen while it is read again.
        claimed.append(True)
        return {**all_, key: current if current is not None and current.status == "done" else Threads("running")}

    m.state.update("threads", claim, default={})
    if claimed:
        m.run(lambda: read(m, number))


def read(m, number: int) -> None:
    """Runs on a background thread: GitHub is asked, and the answer kept in state."""
    def put(value: Threads) -> None:
        m.state.update("threads", lambda all_: {**(all_ or {}), str(number): value}, default={})

    github = m.client("github")
    try:
        if github is None:
            raise RuntimeError("github plugin not available")
        match github.get_pr_review_threads(number, include_resolved=False):
            case ClientSuccess(data=threads):
                put(Threads("done", unresolved=len(threads)))
            case ClientError(error_message=err):
                put(Threads("error", error=err))
    except Exception as e:
        # Never left "running": a count that cannot be read must not look like one being read.
        put(Threads("error", error=str(e)))


def reread_open(m, mine, is_open) -> None:
    """Ask again for the PRs of yours whose row is open: a conversation may have been resolved since."""
    for pr in mine:
        if is_open(pr.number):
            start(m, pr.number)
