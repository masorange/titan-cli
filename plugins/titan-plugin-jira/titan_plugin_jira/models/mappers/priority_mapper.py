"""
Priority Mapper

Maps NetworkJiraPriority (network layer) to UIPriority (view layer).
"""

from ..network.rest.priority import NetworkJiraPriority
from ..view import UIPriority


# Priority icons mapping
PRIORITY_ICONS = {
    "highest": "🔴",
    "high": "🟠",
    "medium": "🟡",
    "low": "🟢",
    "lowest": "⚪",
    "blocker": "🚨",
    "critical": "🔴",
    "major": "🟠",
    "minor": "🟢",
    "trivial": "⚪"
}


def from_network_priority(network_priority: NetworkJiraPriority) -> UIPriority:
    """
    Map NetworkJiraPriority to UIPriority.

    Args:
        network_priority: Network model from API

    Returns:
        UIPriority optimized for rendering
    """
    priority_name_lower = network_priority.name.lower()
    icon = PRIORITY_ICONS.get(priority_name_lower, "⚫")
    label = f"{icon} {network_priority.name}"

    return UIPriority(
        id=network_priority.id,
        name=network_priority.name,
        icon=icon,
        label=label
    )


__all__ = ["from_network_priority"]
