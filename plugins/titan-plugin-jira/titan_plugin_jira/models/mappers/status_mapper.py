"""
Status Mapper

Maps NetworkJiraStatus (network layer) to UIJiraStatus (view layer).
"""

from ..network.rest.status import NetworkJiraStatus
from ..view import UIJiraStatus


# Status category icons mapping
STATUS_CATEGORY_ICONS = {
    "to do": "🟡",
    "new": "🟡",
    "in progress": "🔵",
    "indeterminate": "🔵",
    "done": "🟢",
}


def from_network_status(network_status: NetworkJiraStatus) -> UIJiraStatus:
    """
    Map NetworkJiraStatus to UIJiraStatus.

    Args:
        network_status: Network model from API

    Returns:
        UIJiraStatus optimized for rendering
    """
    category_name = network_status.statusCategory.name if network_status.statusCategory else "To Do"
    category_key = network_status.statusCategory.key if network_status.statusCategory else "new"

    icon = STATUS_CATEGORY_ICONS.get(category_key.lower(), "⚫")
    description = network_status.description or "No description"

    return UIJiraStatus(
        id=network_status.id,
        name=network_status.name,
        description=description,
        category=category_name,
        icon=icon
    )


__all__ = ["from_network_status"]
