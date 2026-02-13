"""
Transition Mapper

Converts Jira REST API transition models to UI view models.
"""

from ..network.rest import NetworkJiraTransition
from ..view import UIJiraTransition
from ..formatting import get_status_icon


def from_network_transition(transition: NetworkJiraTransition) -> UIJiraTransition:
    """
    Convert REST Jira transition to UI transition.

    Args:
        transition: NetworkJiraTransition from REST API

    Returns:
        UIJiraTransition ready for rendering

    Example:
        >>> from ..network.rest import NetworkJiraTransition, NetworkJiraStatus, NetworkJiraStatusCategory
        >>> status = NetworkJiraStatus(id="1", name="In Progress", statusCategory=NetworkJiraStatusCategory(id="2", name="In Progress", key="indeterminate"))
        >>> rest_transition = NetworkJiraTransition(id="1", name="Start Progress", to=status)
        >>> ui_transition = from_network_transition(rest_transition)
        >>> ui_transition.to_status_icon
        '🔵'
    """
    to_status_name = "Unknown"
    to_status_category_key = ""

    if transition.to:
        to_status_name = transition.to.name
        if transition.to.statusCategory:
            to_status_category_key = transition.to.statusCategory.key

    return UIJiraTransition(
        id=transition.id,
        name=transition.name,
        to_status=to_status_name,
        to_status_icon=get_status_icon(to_status_category_key),
    )
