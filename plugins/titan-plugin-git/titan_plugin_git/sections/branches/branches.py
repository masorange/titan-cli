"""The branches to switch to, the switching itself, and pull/push, through the git plugin client."""
from typing import Optional

from titan_cli.core.result import ClientError, ClientSuccess
from titan_plugin_git.operations import filter_branches, match_branch, push_rejected_hint, switch_targets, switching_blocked_by

from titan_plugin_git.readers import Branches

SEARCH_ERROR = "branch_search_error"  # why Enter in the search switched to nothing


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

    every = all_branches(git, current)
    stashes = stash_list(git)

    match git.list_recent_branches(limit=options["recent_branches"]):
        case ClientSuccess(data=branches):
            return Branches(items=list(branches), all=every, current=current, blocked=blocked, main_branch=main, stashes=stashes)
        case ClientError(error_message=err):
            return Branches(all=every, current=current, blocked=blocked, main_branch=main, stashes=stashes, error=err)


def stash_list(git) -> list:
    """The stashes, newest first; empty when git cannot list them (the card then just offers no pop)."""
    match git.list_stashes():
        case ClientSuccess(data=stashes):
            return list(stashes)
        case _:
            return []


def all_branches(git, current: str) -> list:
    """Every local and remote branch a checkout reaches; empty when git cannot list them."""
    lists = []
    for remote in (False, True):
        match git.get_branches(remote=remote):
            case ClientSuccess(data=branches):
                lists.append(list(branches))
            case _:
                lists.append([])
    return switch_targets(lists[0], lists[1], current)


def switch_to_typed(m, query: str) -> None:
    """
    Enter in the search field: switch to the branch the text names - exactly, or as
    the only branch containing it. Anything else is said under the field, and nothing
    is checked out.
    """
    state = m.state.get("branches")
    if state is None:
        return
    if state.blocked:
        m.state.set(SEARCH_ERROR, state.blocked)
        return
    target = match_branch(query, state.all or state.items)
    if target is None:
        found = filter_branches(state.all or state.items, query)
        m.state.set(SEARCH_ERROR, f"{len(found)} branches match; type more of the name" if found else f"No branch named {query.strip()}")
        return
    m.run(lambda: switch_to(m, target.name))


def clear_search(m) -> None:
    """Empty the search field and what it complained about: the list goes back to the recent branches."""
    m.state.set("branch_filter", "")
    m.state.set(SEARCH_ERROR, None)


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
            # The search found what it was for; a name left typed would hide the new list.
            clear_search(m)
            m.state.set("open_branch", None)
            m.ui.toast(f"Switched to {branch}", "information")
        case ClientError(error_message=err):
            m.ui.toast(f"Could not switch to {branch}: {err}", "error")

    refresh = m.state.get("refresh")
    if refresh:
        refresh()


# The two remote actions the pane runs on the branch you are on: what it shows
# while one is in flight, and what the toast says when it ends.
PROGRESS = {"pull": "pulling", "push": "pushing", "stash": "stashing the uncommitted work", "pop": "popping the stash", "apply": "applying the stash",
            "drop": "dropping the stash", "clear": "clearing the stash list"}
DONE = {"pull": "Pulled origin/{branch}", "push": "Pushed {branch} to origin"}
FAILED = {"pull": "Could not pull origin/{branch}", "push": "Could not push {branch}"}
LOCAL = ("stash", "pop", "apply", "drop", "clear")  # act on the tree only: no remote in what the card says while they run


def running(m) -> Optional[str]:
    """The remote action in flight, `"pull"`, `"push"` or None."""
    return m.state.get("remote_action")


def start_remote(m, kind: str, branch: str) -> None:
    """
    Claim the branch and run `kind` on a background thread.

    The button's state is from the last repaint, so two quick presses both saw
    the branch free: claiming in state here closes that window, and the claim is
    what the pane draws its progress line from.
    """
    claimed = []

    def claim(current):
        if current:
            return current
        claimed.append(True)
        return kind

    m.state.update("remote_action", claim)
    if not claimed:
        return
    m.run(lambda: run_remote(m, kind, branch))


def run_remote(m, kind: str, branch: str) -> None:
    """
    Pull or push `branch` against origin and tell the user how it went.

    A refused push is reported as git worded it, with the reason: the pane never
    forces one, since that would throw the remote's commits away on a press. The
    claim is released whatever happens, so a failure never leaves the card stuck
    on its progress line.
    """
    git = m.client("git")
    try:
        if git is None:
            m.ui.toast("git plugin not available", "error")
            return

        result = git.pull("origin", branch) if kind == "pull" else git.push("origin", branch)
        match result:
            case ClientSuccess():
                m.ui.toast(DONE[kind].format(branch=branch), "information")
            case ClientError(error_message=err):
                hint = push_rejected_hint(err) if kind == "push" else None
                message = f"{FAILED[kind].format(branch=branch)}: {err}"
                m.ui.toast(message + (f" {hint}" if hint else ""), "error")
    finally:
        # Cleared before the refresh, so the card goes from the progress line
        # straight to what git says now, in one repaint.
        m.state.set("remote_action", None)
        refresh = m.state.get("refresh")
        if refresh:
            refresh()


def stash_ref(git, commit: str) -> Optional[str]:
    """Where the stash with this commit hash sits in the list now (`stash@{n}`), None when it is gone."""
    match git.list_stashes():
        case ClientSuccess(data=stashes):
            return next((s.ref for s in stashes if s.hash == commit), None)
        case _:
            return None


def start_stash(m, kind: str, ref: Optional[str] = None) -> None:
    """
    Claim the card for `kind` ("stash", "pop", "apply", "drop" or "clear") and run it on a background thread, like a pull or a push.

    `ref` is the stash a pop, apply or drop acts on (`stash@{1}` or its hash); a pop or apply without it takes the latest.
    """
    claimed = []

    def claim(current):
        if current:
            return current
        claimed.append(True)
        return kind

    m.state.update("remote_action", claim)
    if claimed:
        m.run(lambda: run_stash(m, kind, ref))


def run_stash(m, kind: str, ref: Optional[str] = None) -> None:
    """
    Stash everything uncommitted (new files too, so the tree ends up clean), pop, apply or drop one, or clear the stash list.

    A pop that conflicts is reported as git worded it; git keeps the stash then, so nothing is lost.
    """
    git = m.client("git")
    try:
        if git is None:
            m.ui.toast("git plugin not available", "error")
            return

        if kind in ("pop", "apply", "drop") and ref and not ref.startswith("stash@{"):
            # A hash names a stash whatever place it holds; git acts on its place right now.
            ref = stash_ref(git, ref)
            if ref is None:
                m.ui.toast("That stash is gone", "error")
                return

        result = {"stash": lambda: git.stash_push(include_untracked=True), "pop": lambda: git.stash_pop(ref),
                  "apply": lambda: git.stash_apply(ref), "drop": lambda: git.stash_drop(ref),
                  "clear": lambda: git.stash_clear()}[kind]()
        which = ref or "the latest stash"
        done = {"stash": "Stashed the uncommitted work", "pop": f"Popped {which}", "apply": f"Applied {which}",
                "drop": f"Dropped {which}", "clear": "Cleared the stash list"}
        failed = {"stash": "Could not stash", "pop": "Could not pop the stash", "apply": "Could not apply the stash",
                  "drop": "Could not drop the stash", "clear": "Could not clear the stash list"}
        match result:
            case ClientSuccess():
                m.ui.toast(done[kind], "information")
            case ClientError(error_message=err):
                m.ui.toast(f"{failed[kind]}: {err}", "error")
    finally:
        m.state.set("remote_action", None)
        refresh = m.state.get("refresh")
        if refresh:
            refresh()


def create_pr(m, options) -> None:
    """
    Run the PR workflow for the branch you are on.

    Named by option, resolved through `m.workflows`, so a repo extending the
    plugin's workflow gets its own run - the same one its menu entry opens. The
    commit and the push are the workflow's, which is why a dirty tree does not
    hide the button.
    """
    workflow = options.get("create_pr_workflow")
    if not workflow:
        return
    m.workflows.run(workflow)


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
