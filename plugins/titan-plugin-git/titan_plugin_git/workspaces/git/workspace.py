"""
git workspace: a full screen for the repository's history, opened from its dock tile.

The commit graph on the left, led by the uncommitted changes as gitk shows them; on the right the
files of what is selected, each folding into its diff drawn as code. Everything git-specific
(the log, the graph lanes, the per-file diffs) comes from the git plugin client and its readers,
shared with the `git` mod that keeps the summary in the side pane; this file wires reads, timers
and presses and `draw.py` draws from `w.state` only, so it never waits on the network.
"""
from pathlib import Path

from titan_cli.core.result import ClientError
from titan_plugin_git.readers import read_repo
from titan_plugin_git.sections.branches.branches import read_branches, start_stash
from titan_plugin_git.sections.worktrees.worktrees import read_worktrees

from . import draw
from .actions import Actions
from .reading import WIP, FileDiff, Files, card_key, read_file_diff, read_files

TITLE = "Git"


def register(w, on, options):
    started = []

    def put(table, key, value):
        w.state.update(table, lambda rows: {**(rows or {}), key: value}, default={})

    def read_history():
        git = w.client("git")
        root = Path(getattr(git, "repo_path", None) or ".")
        limit = w.state.get("commit_limit") or options["commits_shown"]
        w.state.set("repo", read_repo(git, root, {"recent_commits": limit, "graph_all_branches": True}))

    def read_cards():
        """The branch switcher's and the worktrees' snapshots, read like the git mod's pane reads them."""
        git = w.client("git")
        w.state.set("branches", read_branches(git, options))
        w.state.set("worktrees", read_worktrees(git, Path(getattr(git, "repo_path", None) or "."), options))

    def load_diff(selection, side, path, quiet=False):
        key = card_key(selection, side, path)
        if not quiet:
            put("diffs", key, FileDiff())
        put("diffs", key, read_file_diff(w.client("git"), selection, side, path, options["context_lines"]))

    def open_first(selection, files):
        """A selection shows its first file already open, so the screen opens on code, not on a list."""
        prefix = f"{selection}|"
        if files.groups and not any(k.startswith(prefix) for k in (w.state.get("open") or {})):
            group = files.groups[0]
            first = group.files[0]
            put("open", card_key(selection, group.side, first.path), True)
            load_diff(selection, group.side, first.path)

    def load_files(selection, quiet=False):
        if not quiet:
            put("files", selection, Files())
        files = read_files(w.client("git"), selection)
        put("files", selection, files)
        if files.status == "done" and not quiet:
            open_first(selection, files)

    def refresh_wip():
        """Reread the uncommitted files and the diffs that are open: they are what a commit or an edit changes."""
        first = WIP not in (w.state.get("files") or {})
        load_files(WIP, quiet=not first)
        prefix = f"{WIP}|"
        for key in list((w.state.get("open") or {})):
            if key.startswith(prefix):
                _, side, path = key.split("|", 2)
                load_diff(WIP, side, path, quiet=True)

    def refresh_all():
        read_history()
        read_cards()
        # A popped or dropped stash leaves nothing to show: back to the uncommitted changes, where it landed.
        # A failed read carries no stashes, so it says nothing about this one: keep the selection.
        branches = w.state.get("branches")
        if w.state.get("stash_selected") and branches is not None and not branches.error and not any(
            s.hash == w.state.get("selected") for s in branches.stashes
        ):
            w.state.set("stash_selected", False)
            select(WIP)
        refresh_wip()

    def select_stash(stash):
        select(stash.hash)
        w.state.set("stash_selected", True)
        w.state.set("tab", "stashes")

    def stash_action(kind, stash):
        w.state.set("stash_drop_confirm", None)
        start_stash(w, kind, stash.hash)

    def select(selection):
        w.state.set("stash_selected", False)
        w.state.set("selected", selection)
        files = (w.state.get("files") or {}).get(selection)
        if files is None or files.status == "error":
            w.run(lambda: load_files(selection))
        elif selection == WIP:
            w.run(refresh_wip)

    def toggle(selection, side, f):
        key = card_key(selection, side, f.path)

        def flipped(open_cards):
            cards = dict(open_cards or {})
            if not cards.pop(key, None):
                cards[key] = True
            return cards

        w.state.update("open", flipped, default={})
        shown = (w.state.get("diffs") or {}).get(key)
        if key in (w.state.get("open") or {}) and (shown is None or shown.status == "error"):
            w.run(lambda: load_diff(selection, side, f.path))

    def change_index(kind, paths):
        """Stage, unstage or discard these files of the uncommitted changes, then reread what they changed."""
        w.state.set("discard_confirm", None)

        def run():
            git = w.client("git")
            if git is None:
                w.ui.toast("git plugin not available", "error")
                return
            act = {"stage": git.stage_file, "unstage": git.unstage_file, "discard": git.discard_file}[kind]
            for path in paths:
                match act(path):
                    case ClientError(error_message=err):
                        w.ui.toast(f"Could not {kind} {path}: {err}", "error")
                        break
                    case _:
                        # The card moves to the other group: it stays open where it lands.
                        moved = {"stage": ("unstaged", "staged"), "unstage": ("staged", "unstaged")}.get(kind)
                        if moved:
                            old, new = (card_key(WIP, side, path) for side in moved)
                            if old in (w.state.get("open") or {}):
                                w.state.update("open", lambda cards: {**{k: v for k, v in cards.items() if k != old}, new: True}, default={})
            refresh_wip()

        w.run(run)

    def more_commits():
        w.state.set("commit_limit", (w.state.get("commit_limit") or options["commits_shown"]) + options["commits_shown"])
        w.run(read_history)

    def fewer_commits():
        page = options["commits_shown"]
        w.state.set("commit_limit", max(page, (w.state.get("commit_limit") or page) - page))
        w.run(read_history)

    def resize(widths):
        w.state.set("columns", tuple(widths))
        w.store.set("columns", list(widths))

    actions = Actions(
        select=select,
        toggle=toggle,
        more_commits=more_commits,
        fewer_commits=fewer_commits,
        more_lines=lambda key, limit: put("limits", key, limit + options["diff_lines"]),
        retry_history=lambda: w.run(read_history),
        retry_files=lambda selection: w.run(lambda: load_files(selection)),
        retry_diff=lambda selection, side, f: w.run(lambda: load_diff(selection, side, f.path)),
        copy=w.ui.copy,
        resize=resize,
        stash=stash_action,
        index=change_index,
    )

    w.ui.view(lambda width: draw.draw(w, width, options, actions), title=TITLE)

    def start(w):
        started.append(True)
        # A switch, a pull or a worktree removal changes more than one card, and the press that
        # does it only has `w` to work with: this is how it reaches the refresh.
        w.state.set("refresh", refresh_all)
        w.state.set("pick_stash", select_stash)
        saved = w.store.get("columns")
        if saved and len(saved) == len(draw.DEFAULT_RATIO) and not w.state.get("columns"):
            w.state.set("columns", tuple(saved))
        w.ui.dock(TITLE, on_click=w.ui.open_workspace)
        w.clock.every(options["refresh_seconds"], refresh_all)
        if options.get("refresh_key"):
            w.keys.bind(options["refresh_key"], "Refresh git", lambda: w.run(refresh_all))
        w.run(refresh_all)

    w.on_start(start)

    def focus(w, what):
        """Open on the commit a mod's row pointed at, or on the uncommitted changes."""
        sha = what.get("sha") if isinstance(what, dict) else None
        stash = what.get("stash") if isinstance(what, dict) else None
        if stash:
            select(stash)
            w.state.set("stash_selected", True)
            w.state.set("tab", "stashes")
        elif sha:
            select(sha)
            w.state.set("tab", "history")
        elif not w.state.get("selected"):
            w.state.set("selected", WIP)
        if started:
            w.run(refresh_all)

    w.on_open(focus)

    # A commit, push, pull or checkout is what changes the history and the tree, so reread right
    # after a workflow ends, however it ended. Goes off the workflow's thread, so its end is never delayed.
    @on("workflow.run")
    def after_workflow(w, e, next):
        try:
            return next(e)
        finally:
            if not e.nested and started:
                w.run(refresh_all)
