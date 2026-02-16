"""Mapper for Git status: Network model → UI model."""
from ..network.status import NetworkGitStatus
from ..view.status import UIGitStatus


def from_network_status(network_status: NetworkGitStatus) -> UIGitStatus:
    """
    Transform network status model to UI status model.

    Args:
        network_status: Raw status data from git CLI

    Returns:
        Formatted UI status model with icons and summaries

    Example:
        >>> network = NetworkGitStatus(branch="main", is_clean=False, modified_files=["a.py"], ...)
        >>> ui = from_network_status(network)
        >>> ui.status_summary
        '1 modified'
        >>> ui.clean_icon
        '✗'
    """
    # Clean icon
    clean_icon = "✓" if network_status.is_clean else "✗"

    # Status summary
    if network_status.is_clean:
        status_summary = "Clean"
    else:
        parts = []
        if network_status.modified_files:
            parts.append(f"{len(network_status.modified_files)} modified")
        if network_status.staged_files:
            parts.append(f"{len(network_status.staged_files)} staged")
        if network_status.untracked_files:
            parts.append(f"{len(network_status.untracked_files)} untracked")
        status_summary = ", ".join(parts)

    # Sync status
    sync_status = ""
    if network_status.ahead > 0 and network_status.behind > 0:
        sync_status = f"↑{network_status.ahead} ↓{network_status.behind}"
    elif network_status.ahead > 0:
        sync_status = f"↑{network_status.ahead}"
    elif network_status.behind > 0:
        sync_status = f"↓{network_status.behind}"
    else:
        sync_status = "synced"

    return UIGitStatus(
        branch=network_status.branch,
        is_clean=network_status.is_clean,
        clean_icon=clean_icon,
        status_summary=status_summary,
        modified_files=network_status.modified_files,
        untracked_files=network_status.untracked_files,
        staged_files=network_status.staged_files,
        ahead=network_status.ahead,
        behind=network_status.behind,
        sync_status=sync_status,
    )
