"""Answering a review request from the pane itself: approve, request changes or comment.

GitHub's own review box is what this mirrors. Approve and Request changes go
straight out with no body, as the review-pr workflow submits them; Comment
first opens a field with Accept/Cancel, since an empty comment says nothing,
and posts the PR's general (issue) comment rather than a review.

Sending blocks on the network, so it runs through `m.run`; the pane shows the
action in flight and the PR lists are read again once it lands.
"""
from dataclasses import replace
from typing import Optional

from titan_cli.core.result import ClientError, ClientSuccess

from ...models import Composer

# What the pane shows while the action is in flight, and what the toast says after.
PROGRESS = {"approve": "approving", "request_changes": "requesting changes", "comment": "commenting"}
VERB = {"approve": "approve", "request_changes": "request changes on", "comment": "comment on"}
DONE = {"approve": "Approved", "request_changes": "Changes requested on", "comment": "Commented on"}
# The review events this pane submits; a comment takes the issue-comment path instead.
EVENT = {"approve": "APPROVE", "request_changes": "REQUEST_CHANGES"}


def composer(m) -> Optional[Composer]:
    """The field being written in, if one is open."""
    return m.state.get("composer")


def open_composer(m, number: int, kind: str = "comment") -> None:
    """Open the field for this PR, keeping what was already typed for the same action."""
    current = composer(m)
    same = current is not None and current.number == number and current.kind == kind
    m.state.set("composer", Composer(number=number, kind=kind, text=current.text if same else ""))


def close_composer(m) -> None:
    """Cancel: the row goes back to its buttons and nothing is sent."""
    m.state.set("composer", None)


def write(m, text: str) -> None:
    """Every keystroke in the field; state only, never the network."""
    current = composer(m)
    if current is not None:
        m.state.set("composer", replace(current, text=text))


def submit(m, text: str) -> None:
    """Enter in the field: take the line as typed, then send it."""
    write(m, text)
    send(m)


def send(m) -> None:
    """Accept: send what was written, or say that nothing was."""
    current = composer(m)
    if current is None:
        return
    body = current.text.strip()
    if not body:
        m.ui.toast("Write something first", severity="warning")
        return
    start(m, current.number, current.kind, body)


def running(m, number: int) -> Optional[str]:
    """The action in flight on this PR, if any."""
    return (m.state.get("acting") or {}).get(str(number))


def start(m, number: int, kind: str, body: str = "") -> None:
    """Claim the PR and send on a background thread; a second press while it runs does nothing.

    The button's state is from the last repaint, so two quick presses both saw
    the PR free: claiming in state here closes that window.
    """
    key = str(number)
    claimed = []

    def claim(all_):
        all_ = all_ or {}
        if all_.get(key):
            return all_
        claimed.append(True)
        return {**all_, key: kind}

    m.state.update("acting", claim, default={})
    if not claimed:
        return
    close_composer(m)
    m.run(lambda: _send(m, number, kind, body))


def _send(m, number: int, kind: str, body: str) -> None:
    github = m.client("github")
    try:
        if github is None:
            raise RuntimeError("github plugin not available")
        result = (
            github.add_issue_comment(number, body)
            if kind == "comment"
            else github.submit_review(number, None, EVENT[kind], body)
        )
        match result:
            case ClientSuccess():
                m.ui.toast(f"{DONE[kind]} #{number}")
                refresh(m)
            case ClientError(error_message=err):
                m.ui.toast(f"Could not {VERB[kind]} #{number}: {err}", severity="error")
    except Exception as e:
        m.ui.toast(f"Could not {VERB[kind]} #{number}: {e}", severity="error")
    finally:
        m.state.update("acting", lambda all_: {k: v for k, v in (all_ or {}).items() if k != str(number)}, default={})


def refresh(m) -> None:
    """Read the PR lists again, so the row shows the review state it now has."""
    reread = m.state.get("refresh_prs")
    if reread is not None:
        reread()
