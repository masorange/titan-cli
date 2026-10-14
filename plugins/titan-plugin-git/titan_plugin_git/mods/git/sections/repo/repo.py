"""The branch, its churn and recent commits, through the git plugin client."""
from pathlib import Path

from titan_cli.core.result import ClientError, ClientSuccess

from ...models import Repo


def read_repo(git, root: Path, options) -> Repo:
    if git is None:
        return Repo(branch="(no git)", error="git plugin not available")
    match git.get_status():
        case ClientSuccess(data=status):
            pass
        case ClientError(error_message=err):
            return Repo(branch="(no git)", error=err)

    added = removed = 0
    match git.get_uncommitted_numstat(include_untracked=True):
        case ClientSuccess(data=churns):
            added = sum(c.additions for c in churns)
            removed = sum(c.deletions for c in churns)
        case ClientError():
            pass

    commits = []
    match git.get_commits(str(root), limit=options["recent_commits"]):
        case ClientSuccess(data=log):
            commits = list(log)
        case ClientError():
            pass

    return Repo(
        branch=status.branch,
        has_upstream=status.has_upstream,
        ahead=status.ahead,
        behind=status.behind,
        added=added,
        removed=removed,
        commits=commits,
    )
