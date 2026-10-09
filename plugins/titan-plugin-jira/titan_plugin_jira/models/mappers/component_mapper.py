"""
Component Mapper

Maps NetworkJiraComponent (network layer) to UIJiraComponent (view layer).
"""

from ..network.rest.component import NetworkJiraComponent
from ..view import UIJiraComponent


def from_network_component(network_component: NetworkJiraComponent) -> UIJiraComponent:
    """Map NetworkJiraComponent to UIJiraComponent."""
    return UIJiraComponent(
        id=network_component.id,
        name=network_component.name,
        description=network_component.description or "No description",
    )


__all__ = ["from_network_component"]
