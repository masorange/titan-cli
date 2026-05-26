from titan_plugin_jira.models import UIJiraIssue, UIJiraTransition, UIJiraVersion
from titan_plugin_jira.operations import (
    find_transition_by_name_contains,
    find_transition_by_target_status,
    find_version_by_name,
    issue_has_fix_version,
)


def make_issue(*, fix_versions=None):
    return UIJiraIssue(
        key="TEST-1",
        id="1",
        summary="Test",
        description="Desc",
        status="To Do",
        status_icon="🟡",
        status_category="To Do",
        issue_type="Task",
        issue_type_icon="✅",
        assignee="Unassigned",
        assignee_email=None,
        reporter="Reporter",
        priority="Medium",
        priority_icon="🟡",
        formatted_created_at="01/01/2025 10:00:00",
        formatted_updated_at="01/01/2025 10:00:00",
        labels=[],
        components=[],
        fix_versions=fix_versions or [],
        is_subtask=False,
        parent_key=None,
        subtask_count=0,
    )


def test_find_transition_by_target_status_matches_case_insensitively():
    transitions = [
        UIJiraTransition(id="1", name="Move to QA", to_status="QA", to_status_icon="🟢"),
        UIJiraTransition(id="2", name="Done", to_status="Done", to_status_icon="✅"),
    ]

    result = find_transition_by_target_status(transitions, "qa")

    assert result is not None
    assert result.id == "1"


def test_find_transition_by_name_contains_returns_matching_transition():
    transitions = [
        UIJiraTransition(id="1", name="Move to QA", to_status="QA", to_status_icon="🟢"),
        UIJiraTransition(id="2", name="Done", to_status="Done", to_status_icon="✅"),
    ]

    result = find_transition_by_name_contains(transitions, "qa")

    assert result is not None
    assert result.to_status == "QA"


def test_find_version_by_name_returns_exact_match():
    versions = [
        UIJiraVersion(id="1", name="1.0.0", description="", released=False, release_date="Not set"),
        UIJiraVersion(id="2", name="1.1.0", description="", released=False, release_date="Not set"),
    ]

    result = find_version_by_name(versions, "1.1.0")

    assert result is not None
    assert result.id == "2"


def test_issue_has_fix_version_returns_true_when_present():
    issue = make_issue(fix_versions=["1.0.0", "1.1.0"])

    assert issue_has_fix_version(issue, "1.1.0") is True


def test_issue_has_fix_version_returns_false_when_missing():
    issue = make_issue(fix_versions=["1.0.0"])

    assert issue_has_fix_version(issue, "2.0.0") is False
