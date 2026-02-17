"""Mapper for Git branch: Network model → UI model."""
from ..network.branch import NetworkGitBranch
from ..view.branch import UIGitBranch


def from_network_branch(network_branch: NetworkGitBranch) -> UIGitBranch:
    """
    Transform network branch model to UI branch model.

    Args:
        network_branch: Raw branch data from git CLI

    Returns:
        Formatted UI branch model with display indicators

    Example:
        >>> network = NetworkGitBranch(name="main", is_current=True, upstream="origin/main")
        >>> ui = from_network_branch(network)
        >>> ui.display_name
        '* main'
        >>> ui.upstream_info
        '→ origin/main'
    """
    # Display name with current marker
    display_name = f"* {network_branch.name}" if network_branch.is_current else f"  {network_branch.name}"

    # Upstream info
    upstream_info = ""
    if network_branch.upstream:
        upstream_info = f"→ {network_branch.upstream}"

    return UIGitBranch(
        name=network_branch.name,
        display_name=display_name,
        is_current=network_branch.is_current,
        is_remote=network_branch.is_remote,
        upstream=network_branch.upstream,
        upstream_info=upstream_info,
    )
