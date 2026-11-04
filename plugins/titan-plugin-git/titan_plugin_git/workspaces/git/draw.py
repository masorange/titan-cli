"""The workspace's element tree, drawn from `w.state` only: it never waits on the network."""
from typing import Optional

from titan_cli.ui.components import tabs as tab_strip
from titan_cli.ui.elements import Box, Text, responsive_columns
from titan_plugin_git.readers import Branches, Repo
from titan_plugin_git.sections.branches.draw import stash_list_box
from titan_plugin_git.sections.worktrees.draw import worktrees_list

from .actions import Actions
from .branch import toolbar
from .detail import detail
from .history import history

COLLAPSE_BELOW = 120
DEFAULT_RATIO = (2, 3)
DEFAULT_TAB = "history"


def top_bar(w) -> Box:
    """The branch you are on, how it stands, and the one thing worth doing next."""
    repo: Optional[Repo] = w.state.get("repo")
    branches: Optional[Branches] = w.state.get("branches")
    if repo is None or repo.error:
        return Box(Text("⎇ Git", bold=True, color="info"))
    dirty = bool(branches and branches.blocked)
    status = Text(
        Text(f"⎇ {repo.branch}", bold=True, color="info"),
        repo.has_upstream and Text(f"  ↑{repo.ahead}", color="success" if repo.ahead else "subtle"),
        repo.has_upstream and Text(f" ↓{repo.behind}", color="warning" if repo.behind else "subtle"),
        not repo.has_upstream and Text("  no upstream", dim=True),
        dirty and Text("  ● uncommitted changes", color="warning"),
    )
    return Box(status)


def tab_items(w) -> list:
    """The tabs of the left column, with how many things each holds where that is worth saying."""
    branches: Optional[Branches] = w.state.get("branches")
    worktrees = w.state.get("worktrees")
    stashes = len(branches.stashes) if branches else 0
    trees = len(worktrees.items) if worktrees is not None and not worktrees.error else 0
    return [
        ("history", "History"),
        ("stashes", f"Stashes ({stashes})" if stashes else "Stashes"),
        ("worktrees", f"Worktrees ({trees})" if trees else "Worktrees"),
    ]


def stashes_tab(w) -> Box:
    branches: Optional[Branches] = w.state.get("branches")
    if branches is None:
        return Text("Loading stashes…", dim=True)
    if not branches.stashes:
        return Text("No stashes", dim=True)
    selected = w.state.get("selected") if w.state.get("stash_selected") else None
    return stash_list_box(w, branches, selected=selected or "")


def left(w, width: int, options, actions: Actions) -> Box:
    """The branch's toolbar, and under it one thing at a time under a strip of tabs: the history, the stashes or the worktrees."""
    current = w.state.get("tab") or DEFAULT_TAB
    body = {
        "stashes": lambda: stashes_tab(w),
        "worktrees": lambda: worktrees_list(w, width),
    }.get(current, lambda: history(w, options, actions))
    return Box(toolbar(w, options, width), tab_strip(tab_items(w), current, lambda key: w.state.set("tab", key)), body(), gap=1)


def draw(w, width: int, options, actions: Actions) -> Box:
    return Box(
        top_bar(w),
        responsive_columns(
            width,
            [lambda cw: left(w, cw, options, actions), lambda cw: detail(w, options, actions, cw)],
            ratio=tuple(w.state.get("columns") or DEFAULT_RATIO),
            collapse_below=COLLAPSE_BELOW,
            on_resize=actions.resize,
        ),
        gap=1,
    )
