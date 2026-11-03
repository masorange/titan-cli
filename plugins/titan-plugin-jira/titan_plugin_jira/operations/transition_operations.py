"""
Transition operations

Pure decisions about a Jira transition, on UI models.
"""

from typing import List, Optional

from ..models import UIJiraTransition, UIJiraTransitionField


def resolution_field(transitions: List[UIJiraTransition], status: str) -> Optional[UIJiraTransitionField]:
    """The Resolution a move to `status` requires and Jira lists the values of, or None."""
    for transition in transitions:
        if transition.to_status.strip().lower() == status.strip().lower():
            return next((f for f in transition.required_fields if f.key == "resolution" and f.options), None)
    return None
