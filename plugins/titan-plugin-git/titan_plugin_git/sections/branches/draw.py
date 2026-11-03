"""The branch card and the branch switcher, drawn from `m.state` only; the mod's pane and the workspace both draw them."""
from titan_cli.ui.components import Option, ai_assist_button, choice_card, error_card, fix_prompt
from titan_cli.ui.elements import Box, Button, Input, Text
from titan_plugin_git.drawing import section
from titan_plugin_git.operations import filter_branches, merge_sources
from titan_plugin_git.readers import Branches

from . import branches as branch_actions_api
from . import new_branch as new_branch_api
from .branches import SEARCH_ERROR, clear_search, create_pr, merge_into, switch_to, switch_to_typed

CLEAR_CONFIRM = "stash_clear_confirm"  # the clear-list press is waiting for its second
SEARCH_SHOWN = 12  # matches listed under the search; the rest are counted


def remote_actions(m, branch, options):
    """
    Pull, push and the PR for the branch you are on, as options, or the one line
    saying which of pull and push is running right now.

    Only the current branch: they all act on the checked-out tree, so offering
    them on another row would move the wrong one. While a pull or a push is in
    flight the options are gone, so there is nothing to press twice and the card
    says what it is doing until the toast answers.
    """
    if not branch.is_current:
        return []

    in_flight = branch_actions_api.running(m)
    if in_flight:
        where = "" if in_flight in branch_actions_api.LOCAL else f" origin/{branch.name}"
        return [Text(f"… {branch_actions_api.PROGRESS[in_flight]}{where}", dim=True)]

    # The workflow may live in the github plugin or in the repo: ask for the one
    # that would run, and offer the option only when there is one.
    pr_workflow = options.get("create_pr_workflow") and m.workflows.resolve(options["create_pr_workflow"])

    return [
        Option(f"⇩ Pull origin/{branch.name}", lambda: branch_actions_api.start_remote(m, "pull", branch.name)),
        Option(f"⇧ Push origin/{branch.name}", lambda: branch_actions_api.start_remote(m, "push", branch.name)),
        pr_workflow and Option("⬈ Create PR", lambda: create_pr(m, options)),
    ]


def stash_options(m, branch, state: Branches) -> list:
    """
    Put the uncommitted work aside, and the list of what was put aside: the two ways to
    leave a branch's tree clean and to come back to what was left.

    Only the current branch (they act on the checked-out tree) and only while there is
    something to act on; while a pull, a push or a stash is running the card shows its
    progress line instead.
    """
    if not branch.is_current or branch_actions_api.running(m):
        return []
    return [
        state.blocked and Option("⤓ Stash changes", lambda: branch_actions_api.start_stash(m, "stash")),
        stash_list_option(m, state, f"{new_branch_api.menu_key(branch.name)}:tree"),
    ]


def open_stash(m, stash) -> None:
    """What pressing a stash does: where a screen of its own shows it (the workspace) it is selected, anywhere else the workspace opens on it."""
    pick = m.state.get("pick_stash")
    if pick:
        pick(stash)
    else:
        m.ui.open_workspace("git", focus={"stash": stash.hash})


def stash_list_option(m, state: Branches, menu: str):
    """
    The stashes as a list, newest first, each by its message, branch and age: pressing one shows its
    changes and what can be done with it. A line apart, last, is the way to empty the list, behind a
    second press.
    """
    if not state.stashes:
        return None

    def clear():
        m.state.set(menu, None)
        m.state.set(CLEAR_CONFIRM, False)
        branch_actions_api.start_stash(m, "clear")

    confirming = m.state.get(CLEAR_CONFIRM, False)
    return Option(
        f"⤒ Stashes ({len(state.stashes)})…",
        on_open=lambda: m.state.set(CLEAR_CONFIRM, False),
        content=Box(
            *[
                Button(
                    f"{s.message}" + (f" · {s.branch}" if s.branch else "") + (f" · {s.formatted_date}" if s.formatted_date else ""),
                    lambda s=s: open_stash(m, s),
                )
                for s in state.stashes
            ],
            Text(" "),
            not confirming and Button("✗ Clear stash list…", lambda: m.state.set(CLEAR_CONFIRM, True), dim=True),
            confirming and Text(f"Drops all {len(state.stashes)} stashes. This cannot be undone.", color="warning", wrap=True),
            confirming and Box(
                Button("✓ Confirm clear", clear, variant="error"),
                Button("Cancel", lambda: m.state.set(CLEAR_CONFIRM, False), variant="default"),
                row=True,
            ),
        ),
    )


def new_branch_option(m, branch, options):
    """
    Starting a branch from the one you are on, as a dropdown of the branch's card:
    the field, the AI's suggestion and the checkout.

    Only the current branch, since the new one starts at HEAD and takes the
    uncommitted work with it - which is why it is offered with a dirty tree
    too, and is the way out of having worked on the wrong branch. Nothing is
    created until the press that says so, so a suggestion costs an edit at worst.
    """
    if not branch.is_current:
        return None

    doing = new_branch_api.status(m)
    name = m.state.get(new_branch_api.NAME) or ""
    error = m.state.get(new_branch_api.ERROR)

    return Option(
        "New branch from it…",
        on_open=lambda: new_branch_api.reset(m),
        content=Box(
            Input(
                value=name,
                placeholder="feat/short-description",
                size="normal",
                on_change=lambda value: new_branch_api.set_name(m, value),
                on_submit=lambda value: new_branch_api.create(m, branch.name, options),
            ),
            doing == "suggesting" and Text("… naming the uncommitted work", dim=True),
            doing == "creating" and Text(f"… creating {name}", dim=True),
            not doing and Button(
                "✦ Suggest with AI",
                lambda: new_branch_api.suggest(m, options),
                dim=True,
            ),
            not doing and name and Button(
                f"✓ Create {name} and switch",
                lambda: new_branch_api.create(m, branch.name, options),
                variant="primary",
            ),
            error and error_card(
                error,
                copy=m.ui.copy,
                # Only the model's own failure is worth a CLI session: a taken name or a
                # missing plugin has nothing to debug.
                actions=[ai_assist_button(
                    m,
                    fix_prompt(error, "Titan's git mod asked the AI to suggest a branch name for the uncommitted work and the request failed."),
                    "✦ Fix with AI",
                )] if error.startswith(new_branch_api.AI_ERROR_PREFIX) else [],
            ),
        ),
    )


def branch_actions(m, branch, state: Branches, options, switchable: bool = True, width: int = 40) -> Box:
    """
    What can be done with a branch, under its unfolded line. The branch you are on gets three
    small cards - the working tree (commit, stash), the remote (pull, push, PR) and the branch
    itself (new branch, merge) - and trades the switch for them; any other branch is one card.

    A dirty tree stops a switch and a merge: the header says what it stops, the commit leads the
    working tree's card, and the new branch stays, since it carries the uncommitted work along.
    """
    remote = remote_actions(m, branch, options)
    running = [r for r in remote if isinstance(r, Text)]
    key = new_branch_api.menu_key(branch.name)
    card = dict(width=width - 2, state=m.state, close=False)  # the box's own indent
    blocked = bool(state.blocked)

    # The base branch leads the merge picker, so the usual merge is the first press
    # rather than a second button saying the same thing.
    sources = merge_sources(state.items, branch.name, state.main_branch)
    merges = bool(options.get("merge_workflow"))

    tree = [
        # The way out of the block, first among what is left to press.
        blocked and options.get("commit_workflow") and branch.is_current and Option(
            "✦ Commit with AI", lambda: m.workflows.run(options["commit_workflow"]), "primary"),
        *stash_options(m, branch, state),
    ]
    remotes = [r for r in remote if not isinstance(r, Text)]
    own = [
        switchable and not blocked and Option("⎇ Switch to it", lambda: m.run(lambda: switch_to(m, branch.name))),
        new_branch_option(m, branch, options),
        not blocked and merges and sources and Option("Merge a branch into it…", options=[
            Option(source.name, lambda source=source: merge_into(m, branch.name, source.name, options))
            for source in sources
        ]),
    ]
    titled = branch.is_current

    return Box(
        blocked and Text("commit or stash to use this branch", dim=True),
        running,
        choice_card(tree, key=f"{key}:tree", title="Working tree" if titled else "", **card),
        choice_card(remotes, key=f"{key}:remote", title="Remote" if titled else "", **card),
        choice_card(own, key=key, title="Branch" if titled else "", **card),
        indent=2,
    )


def row_is_open(m, branch, state: Branches) -> bool:
    chosen = m.state.get("open_branch")
    return chosen == branch.name or (chosen is None and branch.is_current and bool(state.blocked))


def branch_row(m, branch, state: Branches, options, switchable: bool = True, width: int = 40) -> Box:
    """
    A branch as a fold: its name, how long ago it was committed to, and what can
    be done with it. Only one row is open at a time, so the card stays short.
    """
    # A dirty tree is what the person has to deal with first, so the branch they are
    # on starts open, holding the way out; closing it is remembered as a choice.
    is_open = row_is_open(m, branch, state)
    title = Text(
        Text("▾ " if is_open else "▸ ", dim=True),
        Text(branch.name, bold=branch.is_current),
        branch.formatted_date and Text(f" · {branch.formatted_date}", dim=True),
        branch.is_current and Text(" · here", dim=True),
        getattr(branch, "is_remote", False) and Text(" · remote", dim=True),
    )
    return Box(
        Button(title, lambda: m.state.set("open_branch", "" if is_open else branch.name)),
        is_open and branch_actions(m, branch, state, options, switchable=switchable, width=width),
    )


def branches_section(m, options, width: int = 40, switcher: bool = True):
    """
    The branch you are on with what can be done with it, and under it the switcher: the branches
    used most recently, and why a switch is refused. `switcher=False` leaves the switcher out.
    """
    branches: Branches = m.state.get("branches")
    if branches is None:
        return section("Loading branches…", "subtle")
    if branches.error and not branches.items:
        return error_card(branches.error, copy=m.ui.copy, title="⎇ Switch branch")

    query = m.state.get("branch_filter", "")
    # The branch you are on cannot be switched to, but it is the usual target of a
    # merge, so it sits above the switcher with its merge actions only.
    current = next((b for b in branches.items if b.is_current), None)
    others = [b for b in branches.items if not b.is_current]
    # With nothing typed the list is the recent branches; a search looks through every
    # branch a checkout reaches, remote-only ones included.
    found = filter_branches(branches.all or others, query) if query.strip() else others
    shown = found[:SEARCH_SHOWN]
    search_error = m.state.get(SEARCH_ERROR)
    is_open = m.state.get("branches_open", False)
    # The card says at a glance whether a switch is possible at all.
    tone = "warning" if branches.blocked else "subtle"

    return Box(
        # Above everything: a dirty tree stops a switch and a merge alike, so the
        # reason belongs where it is read without opening anything.
        branches.blocked and Text(f"⚠ {branches.blocked}", color="warning", wrap=True),
        # The commit lives in the current branch's card; with no such row it stands alone.
        branches.blocked and not current and options.get("commit_workflow") and Button(
            "✦ Commit with AI",
            lambda: m.workflows.run(options["commit_workflow"]),
            variant="primary",
        ),
        current and branch_row(m, current, branches, options, switchable=False, width=width),
        # Where you are and where you could go are two things; an open row's card
        # already leaves a line under it.
        switcher and current and not row_is_open(m, current, branches) and Text(" "),
        # The switcher's own title line is the fold, as the commits one is in the repo card.
        switcher and Button(
            f"{'▾' if is_open else '▸'} Switch branch ({len(others)})",
            lambda: m.state.set("branches_open", not is_open),
            dim=True,
        ),
        switcher and is_open and Box(
            # The search box GitHub's and Jira's workspaces use: three lines with a border.
            Input(
                value=query,
                placeholder="Search or type a branch, Enter to switch",
                size="normal",
                on_change=lambda value: (m.state.set("branch_filter", value), m.state.set(SEARCH_ERROR, None)),
                on_submit=lambda value: switch_to_typed(m, value),
            ),
            query and Button("✕ Clear search", lambda: clear_search(m), dim=True),
            search_error and Text(f"  {search_error}", color="warning", wrap=True),
            not others and not query.strip() and Text("  No other branch", dim=True),
            query.strip() and not found and Text("  No branch matches", dim=True),
            [branch_row(m, b, branches, options, width=width) for b in shown],
            len(found) > SEARCH_SHOWN and Text(f"  …and {len(found) - SEARCH_SHOWN} more; type more of the name", dim=True),
        ),
        border=tone,
    )
