"""What the GitHub mod and the GitHub workspace both read: snapshots of the repo and the readers that build them."""
from . import models, prs, queue, runs  # noqa: F401


def invalidate(github) -> None:
    """Make the next reads go to GitHub: after a change, or when the user asked to read again."""
    if github is not None:
        github.invalidate_reads()
