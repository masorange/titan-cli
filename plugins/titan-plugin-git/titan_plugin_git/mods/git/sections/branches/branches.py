"""The branches to switch to, and the switching itself, through the git plugin client."""
from titan_cli.core.result import ClientError, ClientSuccess
from titan_plugin_git.operations import push_rejected_hint, switching_blocked_by

from ...models import Branches


def read_branches(git, options) -> Branches:
    """The most recently used branches and whether the working tree lets us leave."""
    if git is None:
        return Branches(error="git plugin not available")

    blocked, current = None, ""
    match git.get_status():
        case ClientSuccess(data=status):
            current = status.branch
            blocked = switching_blocked_by(status)
        case ClientError(error_message=err):
            return Branches(error=err)

    main = getattr(git, "main_branch", "") or ""

    match git.list_recent_branches(limit=options["recent_branches"]):
        case ClientSuccess(data=branches):
            return Branches(items=list(branches), current=current, blocked=blocked, main_branch=main)
        case ClientError(error_message=err):
            return Branches(current=current, blocked=blocked, main_branch=main, error=err)


def switch_to(m, branch: str) -> None:
    """
    Check `branch` out and tell the user how it went.

    Runs off the UI thread (`m.run`): the caller is a button press. The pane is
    redrawn from the refresh the mod left in `m.state`, after git has been asked
    again, so what it shows always came from git - a failed checkout included.
    """
    git = m.client("git")
    if git is None:
        m.ui.toast("git plugin not available", "error")
        return

    match git.checkout(branch):
        case ClientSuccess():
            m.ui.toast(f"Switched to {branch}", "information")
        case ClientError(error_message=err):
            m.ui.toast(f"Could not switch to {branch}: {err}", "error")

    refresh = m.state.get("refresh")
    if refresh:
        refresh()


def pull_current(m, branch: str) -> None:
    """
    Bring `branch` up to date with origin and tell the user how it went.

    Runs off the UI thread (`m.run`), like `switch_to`: the pane is redrawn from
    the refresh left in `m.state`, after git has been asked again, so a failed
    pull shows the tree as it really is.
    """
    git = m.client("git")
    if git is None:
        m.ui.toast("git plugin not available", "error")
        return

    match git.pull("origin", branch):
        case ClientSuccess():
            m.ui.toast(f"Pulled origin/{branch}", "information")
        case ClientError(error_message=err):
            m.ui.toast(f"Could not pull origin/{branch}: {err}", "error")

    refresh = m.state.get("refresh")
    if refresh:
        refresh()


def push_current(m, branch: str) -> None:
    """
    Push `branch` to origin and tell the user how it went.

    A refused push is reported as git worded it, with the hint: the pane never
    forces one, since that would throw the remote's commits away on a press.
    """
    git = m.client("git")
    if git is None:
        m.ui.toast("git plugin not available", "error")
        return

    match git.push("origin", branch):
        case ClientSuccess():
            m.ui.toast(f"Pushed {branch} to origin", "information")
        case ClientError(error_message=err):
            hint = push_rejected_hint(err)
            m.ui.toast(f"Could not push {branch}: {err}" + (f" {hint}" if hint else ""), "error")

    refresh = m.state.get("refresh")
    if refresh:
        refresh()


def merge_into(m, target: str, source: str, options) -> None:
    """
    Run the merge workflow: it switches to `target` and merges `source` into it.

    The whole merge - conflicts and all - belongs to the workflow, so the pane
    only asks for it; the refresh after the run is what updates the card.
    """
    workflow = options.get("merge_workflow")
    if not workflow:
        return
    m.workflows.run(workflow, {"target_branch": target, "source_branch": source})
