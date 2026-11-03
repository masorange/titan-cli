"""Transition operations: which required field a move needs the user to pick."""
from titan_plugin_jira.models import UIJiraFieldOption, UIJiraTransition, UIJiraTransitionField
from titan_plugin_jira.operations import resolution_field


def transition(to_status, *fields):
    return UIJiraTransition(id="1", name=to_status, to_status=to_status, to_status_icon="", required_fields=list(fields))


RESOLUTION = UIJiraTransitionField("resolution", "Resolution", True, [UIJiraFieldOption("1", "Done")])


class TestResolutionField:
    def test_returns_the_resolution_of_the_transition_to_that_status(self):
        found = resolution_field([transition("Testing"), transition("Closed", RESOLUTION)], "Closed")

        assert found is RESOLUTION

    def test_status_names_compare_ignoring_case_and_spaces(self):
        assert resolution_field([transition("Closed", RESOLUTION)], " closed ") is RESOLUTION

    def test_none_when_the_status_requires_no_resolution(self):
        assert resolution_field([transition("Testing")], "Testing") is None

    def test_none_when_jira_lists_no_values_to_pick_from(self):
        free_form = UIJiraTransitionField("resolution", "Resolution", True, [])

        assert resolution_field([transition("Closed", free_form)], "Closed") is None

    def test_other_required_fields_are_not_a_resolution(self):
        root_cause = UIJiraTransitionField("customfield_1", "Root Cause", True, [UIJiraFieldOption("1", "Bug")])

        assert resolution_field([transition("Closed", root_cause)], "Closed") is None

    def test_none_for_an_unknown_status(self):
        assert resolution_field([transition("Closed", RESOLUTION)], "Nowhere") is None
