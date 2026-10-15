"""
Version Mapper

Maps NetworkJiraVersion (network layer) to UIJiraVersion (view layer).
"""

from ..network.rest.version import NetworkJiraVersion
from ..view import UIJiraVersion


def from_network_version(network_version: NetworkJiraVersion) -> UIJiraVersion:
    """
    Map NetworkJiraVersion to UIJiraVersion.

    Args:
        network_version: Network model from API

    Returns:
        UIJiraVersion optimized for rendering
    """
    description = network_version.description or "No description"
    start_date = network_version.startDate or "Not set"
    release_date = network_version.releaseDate or "Not set"

    return UIJiraVersion(
        id=network_version.id,
        name=network_version.name,
        description=description,
        released=network_version.released,
        start_date=start_date,
        release_date=release_date
    )


__all__ = ["from_network_version"]
