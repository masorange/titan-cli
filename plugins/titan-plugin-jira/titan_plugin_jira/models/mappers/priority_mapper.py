"""
Priority Mapper

Maps NetworkJiraPriority (network layer) to UIPriority (view layer).
"""

from ..network.rest.priority import NetworkJiraPriority
from ..view import UIPriority
from ..enums import JiraPriority


def from_network_priority(network_priority: NetworkJiraPriority) -> UIPriority:
    """
    Map NetworkJiraPriority to UIPriority.

    Args:
        network_priority: Network model from API

    Returns:
        UIPriority optimized for rendering
    """
    icon = JiraPriority.get_icon(network_priority.name)
    label = f"{icon} {network_priority.name}"

    return UIPriority(
        id=network_priority.id,
        name=network_priority.name,
        icon=icon,
        label=label
    )


__all__ = ["from_network_priority"]
