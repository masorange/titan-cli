"""Snapshots of Jira, each one loading, done or failed, drawn by the mod and the workspace alike."""
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from titan_plugin_jira.models import (
    UIJiraComment,
    UIJiraComponent,
    UIJiraFilter,
    UIJiraIssue,
    UIJiraProject,
    UIJiraStatus,
    UIJiraTransition,
    UIJiraVersion,
)


@dataclass(frozen=True)
class Choices:
    """What the drop-downs offer, as Jira has it."""
    statuses: List[UIJiraStatus] = field(default_factory=list)
    components: List[UIJiraComponent] = field(default_factory=list)
    filters: List[UIJiraFilter] = field(default_factory=list)
    projects: List[UIJiraProject] = field(default_factory=list)
    # Lists ("statuses", "components", "filters", "projects") whose read failed and
    # that nothing earlier could stand in for: absent from the offer is not the same
    # as unknown, so the picks made from them are kept rather than dropped.
    unknown: frozenset = frozenset()


@dataclass(frozen=True)
class Comments:
    """An issue's comments, read when its card opens: loading, done or error."""
    status: str
    items: List[UIJiraComment] = field(default_factory=list)
    error: Optional[str] = None


@dataclass(frozen=True)
class Parent:
    """An issue's parent, read once its child card opens: loading, done or error.
    Cached by parent key, so two children of the same parent share one read."""
    status: str
    issue: Optional[UIJiraIssue] = None
    url: str = ""
    error: Optional[str] = None


@dataclass(frozen=True)
class Transitions:
    """The statuses an issue can move to, read when its picker opens: loading, done or error."""
    status: str
    items: List[UIJiraTransition] = field(default_factory=list)
    error: Optional[str] = None


@dataclass(frozen=True)
class Versions:
    """The versions of an issue's project, read when its fix version picker opens: loading, done or error."""
    status: str
    items: List[UIJiraVersion] = field(default_factory=list)
    error: Optional[str] = None


@dataclass(frozen=True)
class Ready:
    query: str
    issues: List[UIJiraIssue]
    project: str = ""  # empty: every project the user can see
    error: Optional[str] = None
    urls: Dict[str, str] = field(default_factory=dict)  # issue key -> its page
    more: bool = False  # Jira has issues beyond the ones listed
