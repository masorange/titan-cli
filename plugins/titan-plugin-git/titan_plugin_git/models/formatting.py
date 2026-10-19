"""Pure text helpers over git models, shared by mappers and operations."""
import re
from datetime import datetime, timezone
from typing import Optional, Tuple, Union

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


def format_relative(when: Optional[Union[str, datetime]], now: Optional[datetime] = None) -> str:
    """
    How long ago `when` was, short enough for a side pane: "today", "yesterday",
    "3 d", "2 w", "5 mo", "1 y". Empty string when there is no readable date.
    """
    if not when:
        return ""

    moment = when
    if isinstance(moment, str):
        try:
            moment = datetime.fromisoformat(moment.strip().replace(" +", "+").replace("Z", "+00:00"))
        except ValueError:
            return ""

    reference = now or datetime.now(timezone.utc)
    # A naive timestamp is read as local time, which is what git prints without a zone.
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=reference.tzinfo or timezone.utc)
    if reference.tzinfo is None:
        reference = reference.replace(tzinfo=moment.tzinfo)

    days = (reference - moment).days
    if days < 0:
        return "today"
    if days == 0:
        return "today"
    if days == 1:
        return "yesterday"
    if days < 7:
        return f"{days} d"
    if days < 30:
        return f"{days // 7} w"
    if days < 365:
        return f"{days // 30} mo"
    return f"{days // 365} y"


__all__ = ["split_squash_pr_suffix", "format_relative"]
