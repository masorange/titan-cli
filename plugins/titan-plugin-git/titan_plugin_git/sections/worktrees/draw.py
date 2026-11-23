"""The worktrees card, drawn from `m.state` only; the mod's pane and the workspace both draw it."""
from titan_cli.ui.components import Option, choice_card, error_card
from titan_cli.ui.elements import Box, Button, Text
from titan_plugin_git.drawing import section
from titan_plugin_git.readers import Worktrees

from .worktrees import blocked_removal, prune_worktrees, remove_worktree

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


def worktrees_list(m, width: int = 40):
    """The worktrees, one row each folding into its removal, with no card or fold around them."""
    worktrees: Worktrees = m.state.get("worktrees")
    if worktrees is None:
        return Text("Loading worktrees…", dim=True)
    if worktrees.error:
        return error_card(worktrees.error, copy=m.ui.copy, title="⎇ Worktrees")
    return Box(
        not worktrees.items and Text("  No worktrees", dim=True),
        [worktree_row(m, worktrees, w, width) for w in worktrees.items],
        # What git keeps behind when a worktree folder is deleted by hand.
        worktrees.items and Button("⌦ Prune stale records", lambda: m.run(lambda: prune_worktrees(m)), dim=True),
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
