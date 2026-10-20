"""The pane's element tree, drawn from `m.state` only: it never waits on the network."""
from typing import Optional

from titan_cli.core.mods import Box, Button, Input, Text
from titan_plugin_git.models.formatting import split_squash_pr_suffix
from titan_plugin_git.operations import filter_branches, graph_lanes, merge_sources

from .models import Branches, Repo, Worktrees
from .sections.branches import branches as branch_actions_api
from .sections.branches import new_branch as new_branch_api
from .sections.branches.branches import create_pr, merge_into, switch_to
from .sections.worktrees.worktrees import blocked_removal, prune_worktrees, remove_worktree


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
    Pull, push and the PR for the branch you are on, or the one line saying
    which of pull and push is running right now.

    Only the current branch: they all act on the checked-out tree, so offering
    them on another row would move the wrong one. While a pull or a push is in
    flight the buttons are gone, so there is nothing to press twice and the card
    says what it is doing until the toast answers.
    """
    if not branch.is_current:
        return None

    in_flight = branch_actions_api.running(m)
    if in_flight:
        return Text(f"… {branch_actions_api.PROGRESS[in_flight]} origin/{branch.name}", dim=True)

    # The workflow may live in the github plugin or in the repo: ask for the one
    # that would run, and offer the button only when there is one.
    pr_workflow = options.get("create_pr_workflow") and m.workflows.resolve(options["create_pr_workflow"])

    return [
        Button(
            f"⇩ Pull origin/{branch.name}",
            lambda: branch_actions_api.start_remote(m, "pull", branch.name),
            dim=True,
        ),
        Button(
            f"⇧ Push origin/{branch.name}",
            lambda: branch_actions_api.start_remote(m, "push", branch.name),
            dim=True,
        ),
        pr_workflow and Button(
            "⬈ Create PR",
            lambda: create_pr(m, options),
            dim=True,
        ),
    ]


def new_branch_fold(m, branch, options):
    """
    Starting a branch from the one you are on: the field, the AI's suggestion
    and the checkout.

    Only the current branch, since the new one starts at HEAD and takes the
    uncommitted work with it - which is why the fold is offered with a dirty tree
    too, and is the way out of having worked on the wrong branch. Nothing is
    created until the press that says so, so a suggestion costs an edit at worst.
    """
    if not branch.is_current:
        return None

    is_open = m.state.get("new_branch_for") == branch.name
    doing = new_branch_api.status(m)
    name = m.state.get(new_branch_api.NAME) or ""
    error = m.state.get(new_branch_api.ERROR)

    return [
        Button(
            f"{'▾' if is_open else '▸'} New branch from it…",
            lambda: new_branch_api.toggle(m, branch.name),
            dim=True,
        ),
        is_open and Box(
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
            error and Text(error, color="error", wrap=True),
            indent=2,
        ),
    ]


def branch_actions(m, branch, state: Branches, options, switchable: bool = True) -> Box:
    """
    What can be done with a branch, under its unfolded line. The branch you are
    already on trades the switch for a pull and a push.
    """
    if state.blocked:
        # The card's header already says why; this says what it stops. The
        # remote actions stay: a push only sends commits, and git itself refuses
        # the pulls that would overwrite the work and says so in the toast.
        return Box(
            Text("commit or stash to use this branch", dim=True),
            remote_actions(m, branch, options),
            # The way out of having worked on the wrong branch: the new one
            # starts here and carries the uncommitted work with it.
            new_branch_fold(m, branch, options),
            indent=2,
        )

    picking = m.state.get("merge_source_for") == branch.name
    # The base branch leads the picker, so the usual merge is the first press
    # rather than a second button saying the same thing.
    sources = merge_sources(state.items, branch.name, state.main_branch)
    merges = bool(options.get("merge_workflow"))

    return Box(
        switchable and Button("⎇ Switch to it", lambda: m.run(lambda: switch_to(m, branch.name)), dim=True),
        remote_actions(m, branch, options),
        new_branch_fold(m, branch, options),
        merges and sources and Button(
            f"{'▾' if picking else '▸'} Merge a branch into it…",
            lambda: m.state.set("merge_source_for", None if picking else branch.name),
            dim=True,
        ),
        picking and Box(*[
            Button(source.name, lambda source=source: merge_into(m, branch.name, source.name, options), dim=True)
            for source in sources
        ], indent=2),
        indent=2,
    )


def branch_row(m, branch, state: Branches, options, switchable: bool = True) -> Box:
    """
    A branch as a fold: its name, how long ago it was committed to, and what can
    be done with it. Only one row is open at a time, so the card stays short.
    """
    is_open = m.state.get("open_branch") == branch.name
    title = Text(
        Text("▾ " if is_open else "▸ ", dim=True),
        Text(branch.name, bold=branch.is_current),
        branch.formatted_date and Text(f" · {branch.formatted_date}", dim=True),
        branch.is_current and Text(" · here", dim=True),
    )
    return Box(
        Button(title, lambda: m.state.set("open_branch", None if is_open else branch.name)),
        is_open and branch_actions(m, branch, state, options, switchable=switchable),
    )


def branches_section(m, options):
    """The switcher, a card of its own: the branches used most recently, and why a switch is refused."""
    branches: Branches = m.state.get("branches")
    if branches is None:
        return section("Loading branches…", "subtle")
    if branches.error and not branches.items:
        return section(Text("⎇ Switch branch", bold=True, color="error"), "error",
                       Text(branches.error, color="error", wrap=True))

    query = m.state.get("branch_filter", "")
    # The branch you are on cannot be switched to, but it is the usual target of a
    # merge, so it sits above the switcher with its merge actions only.
    current = next((b for b in branches.items if b.is_current), None)
    others = [b for b in branches.items if not b.is_current]
    shown = filter_branches(others, query)
    is_open = m.state.get("branches_open", False)
    # The card says at a glance whether a switch is possible at all.
    tone = "warning" if branches.blocked else "subtle"

    return Box(
        # Above everything: a dirty tree stops a switch and a merge alike, so the
        # reason belongs where it is read without opening anything.
        branches.blocked and Text(f"⚠ {branches.blocked}", color="warning", wrap=True),
        branches.blocked and options.get("commit_workflow") and Button(
            "✦ Commit with AI",
            lambda: m.workflows.run(options["commit_workflow"]),
            variant="primary",
        ),
        current and branch_row(m, current, branches, options, switchable=False),
        current and Text(" "),  # where you are and where you could go are two things
        # The switcher's own title line is the fold, as the commits one is in the repo card.
        Button(
            f"{'▾' if is_open else '▸'} Switch branch ({len(others)})",
            lambda: m.state.set("branches_open", not is_open),
            dim=True,
        ),
        is_open and Box(
            len(others) >= options.get("branch_filter_threshold", 8) and Input(
                value=query,
                placeholder="Filter branches",
                on_change=lambda value: m.state.set("branch_filter", value),
            ),
            not others and Text("  No other branch", dim=True),
            others and not shown and Text("  No branch matches", dim=True),
            [branch_row(m, b, branches, options) for b in shown],
        ),
        border=tone,
    )


def worktree_actions(m, worktrees: Worktrees, worktree) -> Box:
    """What can be done with a worktree, under its unfolded line."""
    blocked = blocked_removal(worktrees, worktree)
    confirming = m.state.get("worktree_confirm") == worktree.path
    forcing = m.state.get("worktree_force") == worktree.path

    return Box(
        Text(worktree.path, dim=True, wrap=True),
        blocked and Text(f"Cannot be removed: {blocked}", dim=True),
        not blocked and Button(
            "✓ Confirm removal" if confirming else "✗ Remove worktree",
            (lambda: m.run(lambda: remove_worktree(m, worktree.path)))
            if confirming
            else (lambda: m.state.set("worktree_confirm", worktree.path)),
            dim=not confirming,
            variant="error" if confirming else None,
        ),
        confirming and Text("The directory is deleted. This cannot be undone.", color="warning", wrap=True),
        # Git refuses a worktree holding work; forcing throws that work away, so it
        # is offered only after git has said no, never as the first thing to press.
        not blocked and forcing and Button(
            "⚠ Force removal (discards its changes)",
            lambda: m.run(lambda: remove_worktree(m, worktree.path, force=True)),
            variant="error",
        ),
        indent=2,
    )


def worktree_row(m, worktrees: Worktrees, worktree) -> Box:
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
        is_open and worktree_actions(m, worktrees, worktree),
    )


def worktrees_section(m, options):
    """The worktrees card: one row per worktree, each folding into its removal."""
    worktrees: Worktrees = m.state.get("worktrees")
    if worktrees is None:
        return section("Loading worktrees…", "subtle")
    if worktrees.error:
        return section(Text("⎇ Worktrees", bold=True, color="error"), "error",
                       Text(worktrees.error, color="error", wrap=True))

    is_open = m.state.get("worktrees_open", False)
    return Box(
        Button(
            f"{'▾' if is_open else '▸'} Worktrees ({len(worktrees.items)})",
            lambda: m.state.set("worktrees_open", not is_open),
            dim=True,
        ),
        is_open and Box(
            not worktrees.items and Text("  No worktrees", dim=True),
            [worktree_row(m, worktrees, w) for w in worktrees.items],
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
        repo.error and Text(repo.error, color="error"),
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
        shown.get("branches", True) and branches_section(m, options or {}),
        shown.get("worktrees", True) and worktrees_section(m, options or {}),
    )
