"""The repository's worktrees, and removing one, through the git plugin client."""
from pathlib import Path

from titan_cli.core.result import ClientError, ClientSuccess
from titan_plugin_git.operations import main_worktree_path, removal_blocked_by

from ...models import Worktrees


def read_worktrees(git, root: Path, options) -> Worktrees:
    """Every worktree of the repository, with the main one and the current one marked."""
    if git is None:
        return Worktrees(error="git plugin not available")

    match git.list_worktrees():
        case ClientSuccess(data=worktrees):
            items = list(worktrees)
            return Worktrees(
                items=items,
                main_path=main_worktree_path(items),
                current_path=str(root),
            )
        case ClientError(error_message=err):
            return Worktrees(error=err)


def blocked_removal(worktrees: Worktrees, worktree) -> str:
    """Why this worktree cannot be removed, or "" when it can."""
    return removal_blocked_by(worktree, worktrees.main_path, worktrees.current_path) or ""


def remove_worktree(m, path: str, force: bool = False) -> None:
    """
    Remove the worktree at `path` and tell the user how it went.

    Runs off the UI thread (`m.run`): the caller is a button press, and this
    deletes a directory. The card is redrawn from the refresh the mod left in
    `m.state`, after git has been asked again.
    """
    git = m.client("git")
    if git is None:
        m.ui.toast("git plugin not available", "error")
        return

    match git.remove_worktree(path, force=force):
        case ClientSuccess():
            m.state.set("worktree_force", None)
            m.ui.toast(f"Worktree removed: {path}", "information")
        case ClientError(error_message=err):
            # Git refuses a worktree with work in it; say so and offer the forced
            # removal on that one row rather than forcing behind the user's back.
            m.state.set("worktree_force", path)
            m.ui.toast(f"Could not remove {path}: {err}", "error")

    m.state.set("worktree_confirm", None)
    refresh = m.state.get("refresh")
    if refresh:
        refresh()


def prune_worktrees(m) -> None:
    """Clear the records git keeps for worktree directories that no longer exist."""
    git = m.client("git")
    if git is None:
        m.ui.toast("git plugin not available", "error")
        return

    match git.prune_worktrees():
        case ClientSuccess(message=message):
            m.ui.toast(message or "Pruned stale worktree metadata", "information")
        case ClientError(error_message=err):
            m.ui.toast(f"Could not prune worktrees: {err}", "error")

    refresh = m.state.get("refresh")
    if refresh:
        refresh()
