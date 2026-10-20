"""The pane's element tree, drawn from `m.state` only: it never waits on the network."""
from typing import Optional

from titan_cli.core.mods import Box, Button, Input, Text
from titan_plugin_git.models.formatting import split_squash_pr_suffix
from titan_plugin_git.operations import filter_branches

from .models import Branches, Repo, Worktrees
from .sections.branches.branches import merge_into, pull_current, switch_to
from .sections.worktrees.worktrees import blocked_removal, prune_worktrees, remove_worktree


def section(title, color: str, *body):
    return Box(title if isinstance(title, Text) else Text(title, bold=True, color=color), *body, border=color)


def commit_line(c) -> Text:
    """A commit by the PR it landed (squash merges) or its hash, its subject without the "(#N)" and its age."""
    subject = split_squash_pr_suffix(c.message_subject)[0]
    return Text("  ", Text(f"#{c.pr_number}", bold=True, color="info") if c.pr_number else Text(c.short_hash, dim=True),
                f" {subject}", Text(f" · {c.formatted_date}", dim=True))


def branch_actions(m, branch, state: Branches, options, switchable: bool = True) -> Box:
    """
    What can be done with a branch, under its unfolded line. The branch you are
    already on offers its merges but no switch.
    """
    if state.blocked:
        # The card's header already says why; this says what it stops. A pull
        # stays: git itself refuses the ones that would overwrite the work, and
        # the toast says so, so a dirty tree is no reason to hide it.
        return Box(
            Text("commit or stash to use this branch", dim=True),
            branch.is_current and Button(
                f"⇩ Pull origin/{branch.name}",
                lambda: m.run(lambda: pull_current(m, branch.name)),
                dim=True,
            ),
            indent=2,
        )

    picking = m.state.get("merge_source_for") == branch.name
    sources = [b for b in state.items if b.name != branch.name]
    main_is_other = state.main_branch and state.main_branch != branch.name
    merges = bool(options.get("merge_workflow"))

    return Box(
        switchable and Button("⎇ Switch to it", lambda: m.run(lambda: switch_to(m, branch.name)), dim=True),
        # Only the branch you are on: `git pull` updates the checked-out tree, so
        # offering it on another branch would quietly pull into the wrong one.
        branch.is_current and Button(
            f"⇩ Pull origin/{branch.name}",
            lambda: m.run(lambda: pull_current(m, branch.name)),
            dim=True,
        ),
        merges and main_is_other and Button(
            f"⤵ Merge {state.main_branch} into it",
            lambda: merge_into(m, branch.name, state.main_branch, options),
            dim=True,
        ),
        merges and sources and Button(
            f"{'▾' if picking else '▸'} Merge another branch…",
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
    return section(
        head,
        "info",
        repo.error and Text(repo.error, color="error"),
        not repo.commits and Text("No commits", dim=True),
        first and Button(label, lambda: m.state.set("commits_open", not commits_open), dim=True),
        commits_open and Box(*[commit_line(c) for c in repo.commits]),
    )


def draw(m, width: int, options=None):
    """One card per section, so each can be turned off on the Mods screen on its own."""
    shown = (options or {}).get("sections", {})
    return Box(
        shown.get("repo", True) and repo_section(m, options),
        shown.get("branches", True) and branches_section(m, options or {}),
        shown.get("worktrees", True) and worktrees_section(m, options or {}),
    )
