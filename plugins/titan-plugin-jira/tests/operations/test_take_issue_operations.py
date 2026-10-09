"""Taking an issue (assign to me + move), and the display helpers the issue pane uses."""
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import Mock

from titan_cli.core.result import ClientError, ClientSuccess
from titan_plugin_jira.operations import (
    assign_issue_to_current_user,
    build_issue_jql,
    components_condition,
    display_lines,
    strip_order_by,
    format_person_name,
    issue_description_lines,
    take_issue,
)


def jira():
    client = Mock()
    client.get_current_user.return_value = ClientSuccess(data=SimpleNamespace(account_id="me-1", display_name="Me"))
    client.assign_issue.return_value = ClientSuccess(data=None)
    client.transition_issue.return_value = ClientSuccess(data=None)
    return client


def test_assign_to_current_user_assigns_by_account_id():
    client = jira()

    result = assign_issue_to_current_user(client, "TEST-1")

    assert isinstance(result, ClientSuccess) and result.data.account_id == "me-1"
    client.assign_issue.assert_called_once_with(issue_key="TEST-1", account_id="me-1")


def test_assign_to_current_user_fails_when_the_user_cannot_be_read():
    client = jira()
    client.get_current_user.return_value = ClientError(error_message="401")

    result = assign_issue_to_current_user(client, "TEST-1")

    assert isinstance(result, ClientError) and "401" in result.error_message
    client.assign_issue.assert_not_called()


def test_take_assigns_then_moves(sample_ui_issue):
    client = jira()
    issue = replace(sample_ui_issue, status="Ready to Dev")

    assert isinstance(take_issue(client, issue, "In Progress"), ClientSuccess)
    client.transition_issue.assert_called_once_with(issue_key="TEST-123", new_status="In Progress")


def test_take_does_not_move_an_issue_already_in_the_status(sample_ui_issue):
    client = jira()

    assert isinstance(take_issue(client, sample_ui_issue, "in progress"), ClientSuccess)
    client.transition_issue.assert_not_called()


def test_take_stops_when_the_assignment_fails(sample_ui_issue):
    client = jira()
    client.assign_issue.return_value = ClientError(error_message="forbidden")

    result = take_issue(client, replace(sample_ui_issue, status="Ready to Dev"), "In Progress")

    assert result.error_message == "Cannot assign TEST-123: forbidden"
    client.transition_issue.assert_not_called()


def test_take_says_the_issue_is_yours_when_only_the_move_fails(sample_ui_issue):
    client = jira()
    client.transition_issue.return_value = ClientError(error_message="no transition")

    result = take_issue(client, replace(sample_ui_issue, status="Ready to Dev"), "In Progress")

    assert isinstance(result, ClientError) and result.error_message.startswith("TEST-123 is yours")


def test_person_names_in_capitals_are_title_cased_and_others_kept():
    assert format_person_name("ALEJANDRO LOPEZ RUIZ") == "Alejandro Lopez Ruiz"
    assert format_person_name("Ana McGil") == "Ana McGil"
    assert format_person_name(None) == ""


def test_description_lines_collapse_blank_runs_and_cut(sample_ui_issue):
    assert issue_description_lines(replace(sample_ui_issue, description="\na\n\n\n\nb  \n")) == ["a", "", "b"]
    long = replace(sample_ui_issue, description="\n".join(str(i) for i in range(50)))
    assert issue_description_lines(long, max_lines=40)[-1] == "…"


def test_description_lines_are_empty_for_the_mapper_placeholder(sample_ui_issue):
    assert issue_description_lines(replace(sample_ui_issue, description="No description")) == []


def test_build_issue_jql_combines_project_status_and_conditions():
    assert build_issue_jql("Ready to Dev", "ECAPP", ["assignee = currentUser()"]) == (
        'project = "ECAPP" AND status = "Ready to Dev" AND (assignee = currentUser()) '
        "ORDER BY priority DESC, updated DESC"
    )
    assert build_issue_jql("Blocked", order_by="") == 'status = "Blocked"'


def test_build_issue_jql_without_a_status_matches_any_status():
    assert build_issue_jql(None, "ECAPP", order_by="") == 'project = "ECAPP"'
    assert build_issue_jql(order_by="") == ""
    assert build_issue_jql() == "ORDER BY priority DESC, updated DESC"


def test_jql_strings_escape_quotes():
    assert build_issue_jql('Say "hi"', order_by="") == 'status = "Say \\"hi\\""'


def test_components_condition_matches_any_of_them():
    assert components_condition(["Android", "iOS"]) == 'component in ("Android", "iOS")'
    assert components_condition([]) == ""


def test_strip_order_by_leaves_only_the_condition():
    assert strip_order_by("project = X AND sprint in openSprints() order by Rank ASC") == "project = X AND sprint in openSprints()"
    assert strip_order_by("ORDER BY created") == ""
    assert strip_order_by("summary ~ border") == "summary ~ border"


def test_display_lines_keep_indentation_and_trim_blank_ends():
    assert display_lines("   \n    code\n\n\n- item  \n\n") == ["    code", "", "- item"]
    assert display_lines(None) == []
    assert display_lines("a\nb\nc", max_lines=2) == ["a", "b", "…"]
