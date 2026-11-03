"""Jira REST API Transition Model"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from .status import NetworkJiraStatus


@dataclass
class NetworkJiraTransitionField:
    """
    One field of a transition's screen, from `expand=transitions.fields`.

    Faithful to API response structure: `allowedValues` are the raw option dicts
    (`{"id", "name"}` or `{"id", "value"}`), whatever the field type offers.
    """
    key: str
    name: str = ""
    required: bool = False
    hasDefaultValue: bool = False
    allowedValues: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class NetworkJiraTransition:
    """
    Jira transition from REST API.

    Faithful to API response structure.
    """
    id: str
    name: str
    to: Optional[NetworkJiraStatus] = None  # Target status
    hasScreen: bool = False
    fields: List[NetworkJiraTransitionField] = field(default_factory=list)  # Only with expand=transitions.fields
