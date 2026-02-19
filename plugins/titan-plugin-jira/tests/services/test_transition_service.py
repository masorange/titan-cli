"""
Unit tests for TransitionService
"""

import pytest
from titan_cli.core.result import ClientSuccess, ClientError
from titan_plugin_jira.clients.services.transition_service import TransitionService
from titan_plugin_jira.exceptions import JiraAPIError


@pytest.fixture
def service(mock_jira_network):
    return TransitionService(mock_jira_network)


@pytest.fixture
def sample_transitions_response():
    """Sample transitions API response"""
    return {
        "transitions": [
            {
                "id": "11",
                "name": "To Do",
                "hasScreen": False,
                "to": {
                    "id": "10000",
                    "name": "To Do",
                    "description": "",
                    "statusCategory": {
                        "id": "2",
                        "name": "To Do",
                        "key": "new",
                        "colorName": "blue-gray"
                    }
                }
            },
            {
                "id": "21",
                "name": "In Progress",
                "hasScreen": False,
                "to": {
                    "id": "10001",
                    "name": "In Progress",
                    "description": "Work in progress",
                    "statusCategory": {
                        "id": "4",
                        "name": "In Progress",
                        "key": "indeterminate",
                        "colorName": "yellow"
                    }
                }
            },
            {
                "id": "31",
                "name": "Done",
                "hasScreen": False,
                "to": {
                    "id": "10002",
                    "name": "Done",
                    "description": "Completed",
                    "statusCategory": {
                        "id": "3",
                        "name": "Done",
                        "key": "done",
                        "colorName": "green"
                    }
                }
            }
        ]
    }


@pytest.mark.unit
class TestTransitionServiceGetTransitions:
    """Test TransitionService.get_transitions()"""

    def test_returns_ui_transition_list(self, service, mock_jira_network, sample_transitions_response):
        """Test maps API response to list of UIJiraTransition"""
        mock_jira_network.make_request.return_value = sample_transitions_response

        result = service.get_transitions("TEST-123")

        assert isinstance(result, ClientSuccess)
        assert len(result.data) == 3
        mock_jira_network.make_request.assert_called_once_with(
            "GET", "issue/TEST-123/transitions"
        )

    def test_ui_transitions_have_correct_status_names(self, service, mock_jira_network, sample_transitions_response):
        """Test each transition carries correct target status name"""
        mock_jira_network.make_request.return_value = sample_transitions_response

        result = service.get_transitions("TEST-123")

        status_names = [t.to_status for t in result.data]
        assert "To Do" in status_names
        assert "In Progress" in status_names
        assert "Done" in status_names

    def test_empty_transitions_returns_empty_list(self, service, mock_jira_network):
        """Test issue with no transitions returns empty list"""
        mock_jira_network.make_request.return_value = {"transitions": []}

        result = service.get_transitions("TEST-123")

        assert isinstance(result, ClientSuccess)
        assert result.data == []

    def test_api_error_returns_client_error(self, service, mock_jira_network):
        """Test API error returns ClientError"""
        mock_jira_network.make_request.side_effect = JiraAPIError("issue not found", status_code=404)

        result = service.get_transitions("MISSING-999")

        assert isinstance(result, ClientError)
        assert result.error_code == "GET_TRANSITIONS_ERROR"


@pytest.mark.unit
class TestTransitionServiceTransitionIssue:
    """Test TransitionService.transition_issue()"""

    def test_transitions_to_valid_status(self, service, mock_jira_network, sample_transitions_response):
        """Test transitions issue when target status is available"""
        mock_jira_network.make_request.side_effect = [
            sample_transitions_response,  # get_transitions call
            None,                         # POST call
        ]

        result = service.transition_issue("TEST-123", "In Progress")

        assert isinstance(result, ClientSuccess)
        # Verify the POST was made with the correct transition id
        post_call = mock_jira_network.make_request.call_args_list[1]
        assert post_call.args[0] == "POST"
        assert "21" == post_call.kwargs["json"]["transition"]["id"]

    def test_invalid_status_returns_error(self, service, mock_jira_network, sample_transitions_response):
        """Test returns ClientError when target status doesn't exist"""
        mock_jira_network.make_request.return_value = sample_transitions_response

        result = service.transition_issue("TEST-123", "Nonexistent Status")

        assert isinstance(result, ClientError)
        assert result.error_code == "INVALID_TRANSITION"
        assert "Nonexistent Status" in result.error_message

    def test_transition_with_comment_adds_comment_payload(self, service, mock_jira_network, sample_transitions_response):
        """Test comment is included in the transition payload"""
        mock_jira_network.make_request.side_effect = [
            sample_transitions_response,
            None,
        ]

        service.transition_issue("TEST-123", "Done", comment="Moving to done")

        post_call = mock_jira_network.make_request.call_args_list[1]
        payload = post_call.kwargs["json"]
        assert "update" in payload
        assert "comment" in payload["update"]

    def test_case_insensitive_status_match(self, service, mock_jira_network, sample_transitions_response):
        """Test status name matching is case-insensitive"""
        mock_jira_network.make_request.side_effect = [
            sample_transitions_response,
            None,
        ]

        result = service.transition_issue("TEST-123", "in progress")

        assert isinstance(result, ClientSuccess)

    def test_api_error_on_post_returns_client_error(self, service, mock_jira_network, sample_transitions_response):
        """Test API error during POST returns ClientError"""
        mock_jira_network.make_request.side_effect = [
            sample_transitions_response,
            JiraAPIError("server error", status_code=500),
        ]

        result = service.transition_issue("TEST-123", "Done")

        assert isinstance(result, ClientError)
        assert result.error_code == "TRANSITION_ERROR"
