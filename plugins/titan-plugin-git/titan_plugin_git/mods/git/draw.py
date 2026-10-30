"""The pane's element tree, drawn from `m.state` only: it never waits on the network."""
from typing import Optional

from titan_cli.ui.elements import Box, Button, Input, Text
from titan_cli.ui.components import Option, ai_assist_button, choice_card, error_card, fix_prompt
from titan_plugin_git.models.formatting import split_squash_pr_suffix
from titan_plugin_git.operations import filter_branches, graph_lanes, merge_sources

from .models import Branches, Repo, Worktrees
from .sections.branches import branches as branch_actions_api
from .sections.branches import new_branch as new_branch_api
from .sections.branches.branches import SEARCH_ERROR, clear_search, create_pr, merge_into, switch_to, switch_to_typed
from .sections.worktrees.worktrees import blocked_removal, prune_worktrees, remove_worktree

SEARCH_SHOWN = 12  # matches listed under the search; the rest are counted


def section(title, color: str, *body):
    return Box(title if isinstance(title, Text) else Text(title, bold=True, color=color), *body, border=color)


# One colour per lane, cycled: what makes a branch followable down the rows.
LANE_COLORS = ("info", "success", "warning", "error", "accent", "primary")


def lane_glyphs(row, width: int) -> Text:
    """A row's lanes, each in its own colour, padded so every subject starts at the same column."""
    cells = list(row.cells) + [" "] * (width - len(row.cells))
    return Text(*[
        Text(cell, color=LANE_COLORS[j % len(LANE_COLORS)], bold=(j == row.lane))
        for j, cell in enumerate(cells)
    ])


def commit_title(c) -> Text:
    """A commit by the PR it landed (squash merges) or its hash, its subject without the "(#N)" and its age."""
    subject = split_squash_pr_suffix(c.message_subject)[0]
    return Text(
        Text(f"#{c.pr_number}", bold=True, color="info") if c.pr_number else Text(c.short_hash, dim=True),
        [Text(f" {ref}", color="accent") for ref in c.refs[:2]],
        f" {subject}",
    )


def commit_detail(m, c, width: int) -> Box:
    """What the commit line leaves out, under it: who wrote it, when, where it is pointed at, and its hash."""
    return Box(
        Text(Text(f"{c.author_short} · {c.date}", dim=True)),
        c.refs and Text(Text(" ".join(c.refs), color="accent", wrap=True)),
        Button("⎘ Copy hash", lambda: m.ui.copy(c.hash, "commit hash"), dim=True),
        indent=width + 1,
    )


def commit_row(m, row, width: int) -> Box:
    """
    One drawn line of the graph: a link row is its lanes alone, a commit row is
    a fold on its subject.

    Only one commit is open at a time, as the branch rows do, so the card keeps
    its height however long the log is.
    """
    if row.is_link:
        return Text(lane_glyphs(row, width))
    c = row.commit
    is_open = m.state.get("open_commit") == c.hash
    return Box(
        Button(
            Text(lane_glyphs(row, width), " ", commit_title(c)),
            lambda: m.state.set("open_commit", None if is_open else c.hash),
        ),
        is_open and commit_detail(m, c, width),
    )


def commit_line(c) -> Text:
    """A commit with no lanes drawn: what the card falls back to when the graph is too wide."""
    return Text("  ", commit_title(c), Text(f" · {c.formatted_date}", dim=True))


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
        return [Text(f"… {branch_actions_api.PROGRESS[in_flight]} origin/{branch.name}", dim=True)]

    # The workflow may live in the github plugin or in the repo: ask for the one
    # that would run, and offer the option only when there is one.
    pr_workflow = options.get("create_pr_workflow") and m.workflows.resolve(options["create_pr_workflow"])

    return [
        Option(f"⇩ Pull origin/{branch.name}", lambda: branch_actions_api.start_remote(m, "pull", branch.name)),
        Option(f"⇧ Push origin/{branch.name}", lambda: branch_actions_api.start_remote(m, "push", branch.name)),
        pr_workflow and Option("⬈ Create PR", lambda: create_pr(m, options)),
    ]


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
    What can be done with a branch, under its unfolded line, in one card. The branch
    you are already on trades the switch for a pull, a push and a PR.
    """
    remote = remote_actions(m, branch, options)
    running = [r for r in remote if isinstance(r, Text)]
    card = dict(width=width - 2, state=m.state, key=new_branch_api.menu_key(branch.name), close=False)  # the box's own indent

    if state.blocked:
        # The card's header already says why; this says what it stops. The
        # remote actions stay: a push only sends commits, and git itself refuses
        # the pulls that would overwrite the work and says so in the toast.
        return Box(
            Text("commit or stash to use this branch", dim=True),
            running,
            # The way out of having worked on the wrong branch: the new one
            # starts here and carries the uncommitted work with it.
            choice_card(
                [
                    # The way out of the block, first among what is left to press.
                    options.get("commit_workflow") and branch.is_current and Option(
                        "✦ Commit with AI", lambda: m.workflows.run(options["commit_workflow"]), "primary"),
                    *(r for r in remote if not isinstance(r, Text)),
                    new_branch_option(m, branch, options),
                ],
                **card,
            ),
            indent=2,
        )

    # The base branch leads the picker, so the usual merge is the first press
    # rather than a second button saying the same thing.
    sources = merge_sources(state.items, branch.name, state.main_branch)
    merges = bool(options.get("merge_workflow"))

    return Box(
        running,
        choice_card(
            [
                switchable and Option("⎇ Switch to it", lambda: m.run(lambda: switch_to(m, branch.name))),
                *(r for r in remote if not isinstance(r, Text)),
                new_branch_option(m, branch, options),
                merges and sources and Option("Merge a branch into it…", options=[
                    Option(source.name, lambda source=source: merge_into(m, branch.name, source.name, options))
                    for source in sources
                ]),
            ],
            **card,
        ),
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


def branches_section(m, options, width: int = 40):
    """The switcher, a card of its own: the branches used most recently, and why a switch is refused."""
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
        current and not row_is_open(m, current, branches) and Text(" "),
        # The switcher's own title line is the fold, as the commits one is in the repo card.
        Button(
            f"{'▾' if is_open else '▸'} Switch branch ({len(others)})",
            lambda: m.state.set("branches_open", not is_open),
            dim=True,
        ),
        is_open and Box(
            Box(
                Input(
                    value=query,
                    placeholder="Search or type a branch, Enter to switch",
                    on_change=lambda value: (m.state.set("branch_filter", value), m.state.set(SEARCH_ERROR, None)),
                    on_submit=lambda value: switch_to_typed(m, value),
                ),
                query and Button("✕", lambda: clear_search(m), dim=True),
                row=True,
            ),
            search_error and Text(f"  {search_error}", color="warning", wrap=True),
            not others and not query.strip() and Text("  No other branch", dim=True),
            query.strip() and not found and Text("  No branch matches", dim=True),
            [branch_row(m, b, branches, options, width=width) for b in shown],
            len(found) > SEARCH_SHOWN and Text(f"  …and {len(found) - SEARCH_SHOWN} more; type more of the name", dim=True),
        ),
        border=tone,
    )


def worktree_actions(m, worktrees: Worktrees, worktree, width: int = 40) -> Box:
    """What can be done with a worktree, under its unfolded line."""
    blocked = blocked_removal(worktrees, worktree)
    confirming = m.state.get("worktree_confirm") == worktree.path
    forcing = m.state.get("worktree_force") == worktree.path
    card_width = width - 2  # the box's own indent

    return Box(
        Text(worktree.path, dim=True, wrap=True),
        blocked and Text(f"Cannot be removed: {blocked}", dim=True),
        not blocked and not confirming and choice_card(
            [Option("✗ Remove worktree", lambda: m.state.set("worktree_confirm", worktree.path))],
            width=card_width,
        ),
        not blocked and confirming and choice_card(
            [
                Option("✓ Confirm removal", lambda: m.run(lambda: remove_worktree(m, worktree.path)), "error"),
                Option("✗ Cancel", lambda: m.state.set("worktree_confirm", None)),
            ],
            width=card_width,
            title="The directory is deleted. This cannot be undone.",
            border="warning",
        ),
        # Git refuses a worktree holding work; forcing throws that work away, so it
        # is offered only after git has said no, never as the first thing to press.
        not blocked and forcing and choice_card(
            [Option("⚠ Force removal (discards its changes)",
                    lambda: m.run(lambda: remove_worktree(m, worktree.path, force=True)), "error")],
            width=card_width,
            border="error",
        ),
        indent=2,
    )


def worktree_row(m, worktrees: Worktrees, worktree, width: int = 40) -> Box:
    """A worktree as a fold: its folder and branch, and what can be done with it."""
    is_open = m.state.get("open_worktree") == worktree.path
    here = blocked_removal(worktrees, worktree) == "the worktree you are in"
    title = Text(
        Text("▾ " if is_open else "▸ ", dim=True),
        f"{worktree.status_icon} {worktree.path_short}",
        worktree.branch_display and Text(f" · {worktree.branch_display}", dim=True),
        here and Text(" · here", dim=True),
    )
    return Box(
        Button(title, lambda: m.state.set("open_worktree", None if is_open else worktree.path)),
        is_open and worktree_actions(m, worktrees, worktree, width),
    )


def worktrees_section(m, options, width: int = 40):
    """The worktrees card: one row per worktree, each folding into its removal."""
    worktrees: Worktrees = m.state.get("worktrees")
    if worktrees is None:
        return section("Loading worktrees…", "subtle")
    if worktrees.error:
        return error_card(worktrees.error, copy=m.ui.copy, title="⎇ Worktrees")

    is_open = m.state.get("worktrees_open", False)
    return Box(
        Button(
            f"{'▾' if is_open else '▸'} Worktrees ({len(worktrees.items)})",
            lambda: m.state.set("worktrees_open", not is_open),
            dim=True,
        ),
        is_open and Box(
            not worktrees.items and Text("  No worktrees", dim=True),
            [worktree_row(m, worktrees, w, width) for w in worktrees.items],
            # What git keeps behind when a worktree folder is deleted by hand.
            worktrees.items and Button("⌦ Prune stale records", lambda: m.run(lambda: prune_worktrees(m)), dim=True),
        ),
        border="subtle",
    )


def commit_step(options) -> int:
    """How many commits a page is: `recent_commits`, or 10 when that is 0 (a page of none could never grow)."""
    return (options or {}).get("recent_commits") or 10


def show_more_commits(m, options):
    """Raise the number of commits read by one page and read them again, off the UI thread."""
    step = commit_step(options)
    m.state.set("commit_limit", (m.state.get("commit_limit") or step) + step)
    m.run(lambda: m.state.get("refresh_repo")())


def repo_section(m, options):
    """The branch you are on, how it stands against its upstream, and the latest commits."""
    repo: Optional[Repo] = m.state.get("repo")
    if repo is None:
        return Text("Loading…", dim=True)

    commits_open = m.state.get("commits_open", False)
    head = Text(
        Text(f"⎇ {repo.branch}", bold=True, color="info"),
        repo.has_upstream and Text(f" ↑{repo.ahead}", color="success" if repo.ahead else "subtle"),
        repo.has_upstream and Text(f" ↓{repo.behind}", color="warning" if repo.behind else "subtle"),
        not repo.has_upstream and Text(" no upstream", dim=True),
        repo.added and Text(f" +{repo.added}", color="success"),
        repo.removed and Text(f" −{repo.removed}", color="error"),
    )
    first = repo.commits[0] if repo.commits else None
    label = f"▾ Last {len(repo.commits)} commits" if commits_open else (
        first and f"▸ {f'#{first.pr_number}' if first.pr_number else first.short_hash} {split_squash_pr_suffix(first.message_subject)[0]}"
    )
    # Past a few lanes the graph eats the subject in a pane this narrow, so the
    # history is shown as a plain list instead of an unreadable one.
    lanes = graph_lanes(repo.rows)
    graphed = repo.rows and lanes <= (options or {}).get("graph_max_lanes", 8)
    return section(
        head,
        "info",
        repo.error and error_card(repo.error, copy=m.ui.copy),
        not repo.commits and Text("No commits", dim=True),
        first and Button(label, lambda: m.state.set("commits_open", not commits_open), dim=True),
        commits_open and Box(*(
            [commit_row(m, row, lanes) for row in repo.rows] if graphed
            else [commit_line(c) for c in repo.commits]
        )),
        # A full page means there may be more behind it; a short one is the whole history.
        commits_open and len(repo.commits) >= (m.state.get("commit_limit") or commit_step(options))
        and Button("＋ Show more", lambda: show_more_commits(m, options), dim=True),
    )


def draw(m, width: int, options=None):
    """One card per section, so each can be turned off on the Mods screen on its own."""
    shown = (options or {}).get("sections", {})
    return Box(
        shown.get("repo", True) and repo_section(m, options),
        shown.get("branches", True) and branches_section(m, options or {}, width),
        shown.get("worktrees", True) and worktrees_section(m, options or {}, width),
    )
