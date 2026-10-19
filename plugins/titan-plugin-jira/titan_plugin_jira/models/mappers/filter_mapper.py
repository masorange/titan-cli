"""
Filter Mapper

Maps NetworkJiraFilter (network layer) to UIJiraFilter (view layer).
"""

from ..network.rest.filter import NetworkJiraFilter
from ..view import UIJiraFilter


def from_network_filter(network_filter: NetworkJiraFilter) -> UIJiraFilter:
    """Map NetworkJiraFilter to UIJiraFilter."""
    return UIJiraFilter(
        id=network_filter.id,
        name=network_filter.name,
        jql=network_filter.jql,
        url=network_filter.viewUrl or "",
    )


__all__ = ["from_network_filter"]
