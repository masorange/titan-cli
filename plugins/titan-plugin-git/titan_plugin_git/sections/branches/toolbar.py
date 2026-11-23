"""
The branch toolbar: the branch you are on, its actions, and the panels they open.

The git workspace draws it above its left column and the git mod's pane under the branch line,
both from their own state.
"""
from dataclasses import dataclass
from typing import Callable, List, Optional

from rich.cells import cell_len

from titan_cli.ui.components import Option, choice_card, error_card
from titan_cli.ui.elements import Box, Button, Input, Text
from titan_plugin_git.operations import filter_branches, merge_sources
from titan_plugin_git.readers import Branches, Repo

from . import branches as api
from . import new_branch as new_branch_api
from .draw import SEARCH_SHOWN, new_branch_form


def can_create_pr(w, options) -> bool:
    return bool(options.get("create_pr_workflow") and w.workflows.resolve(options["create_pr_workflow"]))


PANEL = "branch_panel"  # "switch" or "more": the panel unfolded under the toolbar


def toggle_panel(w, which: str) -> None:
    w.state.update(PANEL, lambda open_: None if open_ == which else which, default=None)


def switch_panel(w, branch, branches: Branches, width: int):
    """The branches to switch to: a search field and the recent ones, or why a switch is refused."""
    name = branch.name if branch else ""
    query = w.state.get("branch_filter", "")
    others = [b for b in branches.items if not b.is_current]
    # With nothing typed the list is the recent branches; a search looks through every branch a checkout reaches.
    found = filter_branches(branches.all or others, query) if query.strip() else others
    shown = [b for b in found[:SEARCH_SHOWN] if b.name != name]
    search_error = w.state.get(api.SEARCH_ERROR)
    title = f"Switch to  ({len(others)} recent)"
    if branches.blocked:
        return choice_card([], width=width, title=title, hint="Commit or stash to switch branch")
    return choice_card(
        [
            Input(
                value=query,
                placeholder="Search or type a branch, Enter to switch",
                size="normal",
                on_change=lambda value: (w.state.set("branch_filter", value), w.state.set(api.SEARCH_ERROR, None)),
                on_submit=lambda value: api.switch_to_typed(w, value),
            ),
            query and Button("✕ Clear search", lambda: api.clear_search(w), dim=True),
            search_error and Text(f"  {search_error}", color="warning", wrap=True),
            not others and not query.strip() and Text("No other branch", dim=True),
            query.strip() and not found and Text("No branch matches", dim=True),
            *[Option(f"{b.name}{' · remote' if getattr(b, 'is_remote', False) else ''}",
                     lambda b=b: w.run(lambda: api.switch_to(w, b.name))) for b in shown],
            len(found) > SEARCH_SHOWN and Text(f"…and {len(found) - SEARCH_SHOWN} more; type more of the name", dim=True),
        ],
        width=width, title=title, state=w.state, key="branch_card:switch",
    )


@dataclass(frozen=True)
class BranchAction:
    """
    One thing the branch's toolbar offers. It either runs at once (`on_press`) or opens a panel
    under the toolbar (`panel`): `body` draws what the panel holds, and `option` the same action as
    a line of the `⋯` menu, for when the row has no room for its button.
    """

    key: str
    label: str
    on_press: Optional[Callable[[], None]] = None
    variant: Optional[str] = None
    body: Optional[Callable[[], object]] = None
    option: Optional[Option] = None

    @property
    def cells(self) -> int:
        """What its button takes on the row: the label, the margin after it and a Titan button's padding."""
        return cell_len(self.label) + (3 if self.variant else 1)


MORE_CELLS = cell_len("⋯ ▾") + 1
CARD_FRAME = 4  # what the card's border and padding take off the column


def fit(actions: List[BranchAction], width: int) -> tuple:
    """The actions whose buttons fit on one row of `width` cells, and the rest, which go behind `⋯`."""
    room = width - CARD_FRAME
    if sum(a.cells for a in actions) <= room:
        return list(actions), []
    shown, used = [], MORE_CELLS
    for action in actions:
        if used + action.cells > room:
            break
        shown.append(action)
        used += action.cells
    return shown, list(actions[len(shown):])


def merge_options(w, branch, sources, options) -> list:
    return [Option(s.name, lambda s=s: api.merge_into(w, branch.name, s.name, options)) for s in sources]


def branch_actions(w, branch, branches: Branches, repo: Optional[Repo], options, width: int) -> List[BranchAction]:
    """The toolbar's actions for the branch you are on, in the order they are shown and given up."""
    name = branch.name
    blocked = branches.blocked
    ahead = repo.ahead if repo and repo.has_upstream else 0
    behind = repo.behind if repo and repo.has_upstream else 0
    sources = merge_sources(branches.items, name, branches.main_branch)
    commit = options.get("commit_workflow")
    pr = can_create_pr(w, options)
    merge = bool(options.get("merge_workflow")) and not blocked and bool(sources)

    def run_commit():
        w.workflows.run(commit)

    def run_pr():
        api.create_pr(w, options)

    return [
        blocked and commit and BranchAction(
            "commit", "✦ Commit", run_commit, "primary", option=Option("✦ Commit with AI", run_commit, "primary")),
        BranchAction("pull", f"⇩ Pull{f' ↓{behind}' if behind else ''}", lambda: api.start_remote(w, "pull", name),
                     option=Option("⇩ Pull", lambda: api.start_remote(w, "pull", name))),
        BranchAction("push", f"⇧ Push{f' ↑{ahead}' if ahead else ''}", lambda: api.start_remote(w, "push", name),
                     option=Option("⇧ Push", lambda: api.start_remote(w, "push", name))),
        pr and BranchAction("pr", "⬈ PR", run_pr, option=Option("⬈ Create PR", run_pr)),
        blocked and BranchAction("stash", "⤓ Stash", lambda: api.start_stash(w, "stash"),
                                 option=Option("⤓ Stash changes", lambda: api.start_stash(w, "stash"))),
        # A new branch carries the uncommitted work along, so a dirty tree does not hide it.
        BranchAction(
            "new", "＋ Branch",
            body=lambda: Box(new_branch_form(w, branch, options), border="subtle"),
            option=Option("＋ New branch from here…", on_open=lambda: new_branch_api.reset(w), content=new_branch_form(w, branch, options)),
        ),
        merge and BranchAction(
            "merge", "⇄ Merge",
            body=lambda: choice_card(merge_options(w, branch, sources, options), width=width, title=f"Merge into {name}",
                                     state=w.state, key="branch_card:merge"),
            option=Option("⇄ Merge a branch into it…", options=merge_options(w, branch, sources, options)),
        ),
    ]


def toolbar(w, options, width: int = 40) -> Box:
    """
    The branch you are on as a selector and, under it, a row with every action on it; the ones the
    row has no room for are grouped behind `⋯`. The panel one of them opened goes under the card.
    A running pull, push or stash replaces the buttons with what it is doing.
    """
    branches: Optional[Branches] = w.state.get("branches")
    repo: Optional[Repo] = w.state.get("repo")
    if branches is None:
        return Text("Loading branches…", dim=True)
    if branches.error and not branches.items:
        return error_card(branches.error, copy=w.ui.copy, title="⎇ Branch")
    branch = next((b for b in branches.items if b.is_current), None)
    panel = w.state.get(PANEL)
    blocked = branches.blocked
    in_flight = api.running(w)
    name = branch.name if branch else ""

    selector = Button(
        Text(Text("⎇ ", color="info"), Text(name or "no branch checked out", bold=True, color="info"), f" {'▴' if panel == 'switch' else '▾'}"),
        lambda: toggle_panel(w, "switch"),
    )
    row = None
    shown, hidden = [], []
    if branch is not None and in_flight:
        where = "" if in_flight in api.LOCAL else f" origin/{name}"
        row = Text(f"… {api.PROGRESS[in_flight]}{where}", dim=True)
    elif branch is not None:
        shown, hidden = fit([a for a in branch_actions(w, branch, branches, repo, options, width) if a], width)
        row = Box(
            *[Button(a.label, a.on_press or (lambda a=a: toggle_panel(w, a.key)), variant=a.variant) for a in shown],
            hidden and Button(f"⋯ {'▴' if panel == 'more' else '▾'}", lambda: toggle_panel(w, "more")),
            row=True, pack=True,
        )

    opened = next((a for a in shown if a.key == panel and a.body), None)
    return Box(
        Box(
            selector,
            row,
            blocked and Text(f"⚠ {blocked}", color="warning", wrap=True),
            border="warning" if blocked else "subtle",
        ),
        panel == "switch" and switch_panel(w, branch, branches, width),
        panel == "more" and hidden and choice_card(
            [a.option for a in hidden], width=width, title="More", state=w.state,
            key=new_branch_api.menu_key(name), close=False,
        ),
        opened and opened.body(),
    )
