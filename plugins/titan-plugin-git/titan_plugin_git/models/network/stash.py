"""Network model for a Git stash - faithful to git CLI output."""
from dataclasses import dataclass


@dataclass
class NetworkGitStash:
    """
    One line of `git stash list`, split as git prints it.

    `ref` is the reflog name (`stash@{0}`), `subject` the reflog subject exactly as git
    wrote it ("On feat/x: my message" or "WIP on feat/x: abc1234 last commit"), and
    `relative_date` git's own "2 hours ago", `commit` the hash behind `ref`. No parsing of the subject here.
    """

    ref: str
    subject: str
    relative_date: str = ""
    commit: str = ""  # the stash commit's hash: stable while the list shifts under `ref`
