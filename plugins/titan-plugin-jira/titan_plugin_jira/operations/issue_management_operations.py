"""Pure operations for reusable Jira issue management capabilities."""

from titan_plugin_jira.models import UIJiraIssue, UIJiraTransition, UIJiraVersion


def find_transition_by_target_status(
    transitions: list[UIJiraTransition], target_status: str
) -> UIJiraTransition | None:
    """Return the transition whose target status matches the requested status."""
    target = target_status.strip().lower()
    return next((t for t in transitions if t.to_status.strip().lower() == target), None)


def find_transition_by_name_contains(
    transitions: list[UIJiraTransition], needle: str
) -> UIJiraTransition | None:
    """Return the first transition whose name contains the provided text."""
    normalized = needle.strip().lower()
    return next((t for t in transitions if normalized in t.name.strip().lower()), None)


def find_version_by_name(
    versions: list[UIJiraVersion], version_name: str
) -> UIJiraVersion | None:
    """Return the Jira version with the exact requested name."""
    target = version_name.strip()
    return next((v for v in versions if v.name == target), None)


def issue_has_fix_version(issue: UIJiraIssue, version_name: str) -> bool:
    """Check whether a Jira issue already contains the requested fixVersion."""
    target = version_name.strip()
    return target in issue.fix_versions
