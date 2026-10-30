"""
Transition Mapper

Converts Jira REST API transition models to UI view models.
"""

from ..network.rest import NetworkJiraTransition, NetworkJiraTransitionField
from ..view import UIJiraFieldOption, UIJiraTransition, UIJiraTransitionField
from ..formatting import get_status_icon


def _option_label(option: dict) -> str:
    """Jira names an option `name` (resolution, priority) or `value` (select lists)."""
    return str(option.get("name") or option.get("value") or option.get("id") or "")


def from_network_transition_field(field: NetworkJiraTransitionField) -> UIJiraTransitionField:
    """Convert one field of a transition's screen to its UI model."""
    return UIJiraTransitionField(
        key=field.key,
        name=field.name or field.key,
        required=field.required,
        options=[
            UIJiraFieldOption(id=str(o["id"]), label=_option_label(o))
            for o in field.allowedValues if o.get("id") is not None
        ],
    )


def from_network_transition(transition: NetworkJiraTransition) -> UIJiraTransition:
    """
    Convert REST Jira transition to UI transition.

    Args:
        transition: NetworkJiraTransition from REST API

    Returns:
        UIJiraTransition ready for rendering
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
        required_fields=[from_network_transition_field(f) for f in transition.fields if f.required and not f.hasDefaultValue],
    )
