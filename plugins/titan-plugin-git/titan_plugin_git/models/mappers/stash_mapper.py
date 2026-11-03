"""Mapper for Git stash: Network model → UI model."""
from ..network.stash import NetworkGitStash
from ..view.stash import UIGitStash


def from_network_stash(network_stash: NetworkGitStash) -> UIGitStash:
    """
    Transform a network stash into the UI model.

    The reflog subject is "On <branch>: <message>" for a stash made with a message and
    "WIP on <branch>: <sha> <subject>" for one made without; anything else is kept whole
    as the message.
    """
    subject = network_stash.subject
    branch, message = "", subject
    for prefix in ("WIP on ", "On "):
        if subject.startswith(prefix) and ": " in subject:
            branch, message = subject[len(prefix):].split(": ", 1)
            break
    return UIGitStash(
        ref=network_stash.ref,
        branch=branch,
        message=message,
        formatted_date=network_stash.relative_date,
        hash=network_stash.commit,
    )
