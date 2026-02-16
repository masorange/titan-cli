"""Mapper for Git tag: Network model → UI model."""
from ..network.tag import NetworkGitTag
from ..view.tag import UIGitTag


def from_network_tag(network_tag: NetworkGitTag) -> UIGitTag:
    """
    Transform network tag model to UI tag model.

    Args:
        network_tag: Raw tag data from git CLI

    Returns:
        Formatted UI tag model with icon and short hash

    Example:
        >>> network = NetworkGitTag(name="v1.0.0", commit_hash="abc123...", message="Release v1.0.0")
        >>> ui = from_network_tag(network)
        >>> ui.display_name
        '🏷  v1.0.0'
        >>> ui.commit_hash_short
        'abc1234'
    """
    # Display name with tag icon
    display_name = f"🏷  {network_tag.name}"

    # Short commit hash
    commit_hash_short = None
    if network_tag.commit_hash:
        commit_hash_short = (
            network_tag.commit_hash[:7]
            if len(network_tag.commit_hash) >= 7
            else network_tag.commit_hash
        )

    # Message summary (first line)
    message_summary = None
    if network_tag.message:
        message_summary = network_tag.message.split('\n')[0]

    return UIGitTag(
        name=network_tag.name,
        display_name=display_name,
        commit_hash=network_tag.commit_hash,
        commit_hash_short=commit_hash_short,
        message=network_tag.message,
        message_summary=message_summary,
    )
