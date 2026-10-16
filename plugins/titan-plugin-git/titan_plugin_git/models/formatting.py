"""Pure text helpers over git models, shared by mappers and operations."""
import re
from typing import Optional, Tuple

_SQUASH_PR_SUFFIX = re.compile(r"\s*\(#(\d+)\)$")


def split_squash_pr_suffix(subject: str) -> Tuple[str, Optional[int]]:
    """
    Split the "(#1234)" GitHub appends to a squash merge's subject: the subject
    without it, and the PR the commit landed (None when there is no suffix).
    """
    match = _SQUASH_PR_SUFFIX.search(subject)
    if not match:
        return subject, None
    return subject[: match.start()], int(match.group(1))


__all__ = ["split_squash_pr_suffix"]
