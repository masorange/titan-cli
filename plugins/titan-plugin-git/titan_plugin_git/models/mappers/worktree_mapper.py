"""Mapper for Git worktree: Network model → UI model."""
import os
from ..network.worktree import NetworkGitWorktree
from ..view.worktree import UIGitWorktree


def from_network_worktree(network_worktree: NetworkGitWorktree) -> UIGitWorktree:
    """
    Transform network worktree model to UI worktree model.

    Args:
        network_worktree: Raw worktree data from git CLI

    Returns:
        Formatted UI worktree model with icons and short paths

    Example:
        >>> network = NetworkGitWorktree(path="/home/user/project", branch="main", commit="abc123...")
        >>> ui = from_network_worktree(network)
        >>> ui.status_icon
        '📂'
        >>> ui.branch_display
        'main'
    """
    # Short path (just basename for now, could make relative)
    path_short = os.path.basename(network_worktree.path) or network_worktree.path

    # Branch display
    if network_worktree.is_bare:
        branch_display = "(bare)"
    elif network_worktree.is_detached:
        branch_display = "(detached)"
    elif network_worktree.branch:
        branch_display = network_worktree.branch
    else:
        branch_display = ""

    # Short commit hash
    commit_short = None
    if network_worktree.commit:
        commit_short = (
            network_worktree.commit[:7]
            if len(network_worktree.commit) >= 7
            else network_worktree.commit
        )

    # Status icon
    if network_worktree.is_bare:
        status_icon = "📦"
    elif network_worktree.is_detached:
        status_icon = "🔓"
    else:
        status_icon = "📂"

    return UIGitWorktree(
        path=network_worktree.path,
        path_short=path_short,
        branch=network_worktree.branch,
        branch_display=branch_display,
        commit=network_worktree.commit,
        commit_short=commit_short,
        is_bare=network_worktree.is_bare,
        is_detached=network_worktree.is_detached,
        status_icon=status_icon,
    )
