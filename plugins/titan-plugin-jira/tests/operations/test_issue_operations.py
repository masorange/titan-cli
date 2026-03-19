"""
Tests for Issue Operations

Tests for pure business logic related to issue operations.
"""

import pytest
from unittest.mock import Mock
from titan_cli.core.result import ClientSuccess, ClientError
from titan_plugin_jira.operations.issue_operations import (
    find_ready_to_dev_transition,
    transition_issue_to_ready_for_dev,
    find_issue_type_by_name,
    prepare_epic_name,
    find_subtask_issue_type,
)
from titan_plugin_jira.models import UIJiraTransition
from titan_plugin_jira.models.network.rest.issue_type import NetworkJiraIssueType


class TestFindReadyToDevTransition:
    """Tests for find_ready_to_dev_transition function."""

    def test_finds_ready_to_dev_transition(self):
        """Should find 'Ready to Dev' transition when it exists."""
        # Setup
        mock_client = Mock()
        transitions = [
            UIJiraTransition(
                id="11",
                name="Start Progress",
                to_status="In Progress",
                to_status_icon="🔵",
            ),
            UIJiraTransition(
                id="21", name="Ready to Dev", to_status="Ready to Dev", to_status_icon="🔵"
            ),
            UIJiraTransition(id="31", name="Done", to_status="Done", to_status_icon="🟢"),
        ]
        mock_client.get_transitions.return_value = ClientSuccess(data=transitions)

        # Execute
        result = find_ready_to_dev_transition(mock_client, "TEST-123")

        # Assert
        assert isinstance(result, ClientSuccess)
        assert result.data.name == "Ready to Dev"
        assert result.data.to_status == "Ready to Dev"
        mock_client.get_transitions.assert_called_once_with("TEST-123")

    def test_finds_ready_for_development_variation(self):
        """Should find variations like 'Ready for Development'."""
        # Setup
        mock_client = Mock()
        transitions = [
            UIJiraTransition(
                id="21",
                name="Ready for Development",
                to_status="Ready for Dev",
                to_status_icon="🔵",
            ),
        ]
        mock_client.get_transitions.return_value = ClientSuccess(data=transitions)

        # Execute
        result = find_ready_to_dev_transition(mock_client, "TEST-123")

        # Assert
        assert isinstance(result, ClientSuccess)
        assert result.data.name == "Ready for Development"

    def test_case_insensitive_matching(self):
        """Should match regardless of case."""
        # Setup
        mock_client = Mock()
        transitions = [
            UIJiraTransition(
                id="21", name="READY TO DEV", to_status="Ready to Dev", to_status_icon="🔵"
            ),
        ]
        mock_client.get_transitions.return_value = ClientSuccess(data=transitions)

        # Execute
        result = find_ready_to_dev_transition(mock_client, "TEST-123")

        # Assert
        assert isinstance(result, ClientSuccess)

    def test_transition_not_found(self):
        """Should return error when transition not found."""
        # Setup
        mock_client = Mock()
        transitions = [
            UIJiraTransition(
                id="11",
                name="Start Progress",
                to_status="In Progress",
                to_status_icon="🔵",
            ),
            UIJiraTransition(id="31", name="Done", to_status="Done", to_status_icon="🟢"),
        ]
        mock_client.get_transitions.return_value = ClientSuccess(data=transitions)

        # Execute
        result = find_ready_to_dev_transition(mock_client, "TEST-123")

        # Assert
        assert isinstance(result, ClientError)
        assert "TRANSITION_NOT_FOUND" in result.error_code
        assert "Ready to Dev" in result.error_message

    def test_empty_transitions_list(self):
        """Should return error when no transitions available."""
        # Setup
        mock_client = Mock()
        mock_client.get_transitions.return_value = ClientSuccess(data=[])

        # Execute
        result = find_ready_to_dev_transition(mock_client, "TEST-123")

        # Assert
        assert isinstance(result, ClientError)
        assert "TRANSITION_NOT_FOUND" in result.error_code

    def test_api_error_propagated(self):
        """Should propagate error from get_transitions."""
        # Setup
        mock_client = Mock()
        error = ClientError(
            error_message="API connection failed", error_code="CONNECTION_ERROR"
        )
        mock_client.get_transitions.return_value = error

        # Execute
        result = find_ready_to_dev_transition(mock_client, "TEST-123")

        # Assert
        assert isinstance(result, ClientError)
        assert result.error_code == "CONNECTION_ERROR"
        assert "API connection failed" in result.error_message

    def test_partial_match_not_accepted(self):
        """Should not match transitions that don't contain both 'ready' and 'dev'."""
        # Setup
        mock_client = Mock()
        transitions = [
            UIJiraTransition(
                id="11", name="Ready to Start", to_status="Ready", to_status_icon="🟡"
            ),
            UIJiraTransition(
                id="21", name="In Development", to_status="In Dev", to_status_icon="🔵"
            ),
        ]
        mock_client.get_transitions.return_value = ClientSuccess(data=transitions)

        # Execute
        result = find_ready_to_dev_transition(mock_client, "TEST-123")

        # Assert
        assert isinstance(result, ClientError)
        assert "TRANSITION_NOT_FOUND" in result.error_code


class TestTransitionIssueToReadyForDev:
    """Tests for transition_issue_to_ready_for_dev function."""

    def test_successful_transition(self):
        """Should successfully transition issue when transition exists."""
        # Setup
        mock_client = Mock()
        transition = UIJiraTransition(
            id="21", name="Ready to Dev", to_status="Ready to Dev", to_status_icon="🔵"
        )

        # Mock find operation
        mock_client.get_transitions.return_value = ClientSuccess(data=[transition])

        # Mock transition execution
        mock_client.transition_issue.return_value = ClientSuccess(
            data=None, message="Transition successful"
        )

        # Execute
        result = transition_issue_to_ready_for_dev(mock_client, "TEST-123")

        # Assert
        assert isinstance(result, ClientSuccess)
        mock_client.transition_issue.assert_called_once_with(
            issue_key="TEST-123", new_status="Ready to Dev"
        )

    def test_transition_not_found(self):
        """Should return error when transition not found."""
        # Setup
        mock_client = Mock()
        mock_client.get_transitions.return_value = ClientSuccess(
            data=[
                UIJiraTransition(
                    id="11",
                    name="Start Progress",
                    to_status="In Progress",
                    to_status_icon="🔵",
                )
            ]
        )

        # Execute
        result = transition_issue_to_ready_for_dev(mock_client, "TEST-123")

        # Assert
        assert isinstance(result, ClientError)
        assert "TRANSITION_NOT_FOUND" in result.error_code
        # Should NOT call transition_issue since transition wasn't found
        mock_client.transition_issue.assert_not_called()

    def test_transition_execution_fails(self):
        """Should return error when transition execution fails."""
        # Setup
        mock_client = Mock()
        transition = UIJiraTransition(
            id="21", name="Ready to Dev", to_status="Ready to Dev", to_status_icon="🔵"
        )

        # Mock successful find
        mock_client.get_transitions.return_value = ClientSuccess(data=[transition])

        # Mock failed transition
        error = ClientError(
            error_message="Insufficient permissions", error_code="PERMISSION_DENIED"
        )
        mock_client.transition_issue.return_value = error

        # Execute
        result = transition_issue_to_ready_for_dev(mock_client, "TEST-123")

        # Assert
        assert isinstance(result, ClientError)
        assert result.error_code == "PERMISSION_DENIED"
        assert "Insufficient permissions" in result.error_message

    def test_api_error_when_getting_transitions(self):
        """Should return error when get_transitions fails."""
        # Setup
        mock_client = Mock()
        error = ClientError(error_message="Network error", error_code="NETWORK_ERROR")
        mock_client.get_transitions.return_value = error

        # Execute
        result = transition_issue_to_ready_for_dev(mock_client, "TEST-123")

        # Assert
        assert isinstance(result, ClientError)
        assert result.error_code == "NETWORK_ERROR"
        # Should NOT attempt transition
        mock_client.transition_issue.assert_not_called()

    def test_works_with_different_case(self):
        """Should work with different case variations."""
        # Setup
        mock_client = Mock()
        transition = UIJiraTransition(
            id="21",
            name="READY FOR DEVELOPMENT",
            to_status="Ready for Dev",
            to_status_icon="🔵",
        )

        mock_client.get_transitions.return_value = ClientSuccess(data=[transition])
        mock_client.transition_issue.return_value = ClientSuccess(
            data=None, message="Success"
        )

        # Execute
        result = transition_issue_to_ready_for_dev(mock_client, "TEST-123")

        # Assert
        assert isinstance(result, ClientSuccess)
        mock_client.transition_issue.assert_called_once_with(
            issue_key="TEST-123", new_status="Ready for Dev"
        )


class TestFindIssueTypeByName:
    """Tests for find_issue_type_by_name function."""

    def test_finds_issue_type_case_insensitive(self):
        """Should find issue type with case-insensitive match."""
        # Setup
        mock_client = Mock()
        issue_types = [
            NetworkJiraIssueType(id="1", name="Bug", subtask=False),
            NetworkJiraIssueType(id="2", name="Story", subtask=False),
            NetworkJiraIssueType(id="3", name="Task", subtask=False),
        ]
        mock_client.get_issue_types.return_value = ClientSuccess(data=issue_types)

        # Execute
        result = find_issue_type_by_name(mock_client, "PROJ", "bug")

        # Assert
        assert isinstance(result, ClientSuccess)
        assert result.data.id == "1"
        assert result.data.name == "Bug"
        mock_client.get_issue_types.assert_called_once_with("PROJ")

    def test_issue_type_not_found(self):
        """Should return error when issue type not found."""
        # Setup
        mock_client = Mock()
        issue_types = [
            NetworkJiraIssueType(id="1", name="Bug", subtask=False),
            NetworkJiraIssueType(id="2", name="Story", subtask=False),
        ]
        mock_client.get_issue_types.return_value = ClientSuccess(data=issue_types)

        # Execute
        result = find_issue_type_by_name(mock_client, "PROJ", "Epic")

        # Assert
        assert isinstance(result, ClientError)
        assert "Epic" in result.error_message
        assert "Bug, Story" in result.error_message
        assert result.error_code == "INVALID_ISSUE_TYPE"

    def test_propagates_api_error(self):
        """Should propagate API error from get_issue_types."""
        # Setup
        mock_client = Mock()
        mock_client.get_issue_types.return_value = ClientError(
            error_message="API Error", error_code="API_ERROR"
        )

        # Execute
        result = find_issue_type_by_name(mock_client, "PROJ", "Bug")

        # Assert
        assert isinstance(result, ClientError)
        assert result.error_message == "API Error"


class TestPrepareEpicName:
    """Tests for prepare_epic_name function."""

    def test_returns_summary_for_epic(self):
        """Should return summary when issue type is Epic."""
        # Setup
        epic_type = NetworkJiraIssueType(id="10", name="Epic", subtask=False)

        # Execute
        result = prepare_epic_name(epic_type, "My Epic Summary")

        # Assert
        assert result == "My Epic Summary"

    def test_returns_none_for_non_epic(self):
        """Should return None when issue type is not Epic."""
        # Setup
        bug_type = NetworkJiraIssueType(id="1", name="Bug", subtask=False)

        # Execute
        result = prepare_epic_name(bug_type, "My Bug Summary")

        # Assert
        assert result is None

    def test_case_insensitive_epic_check(self):
        """Should work with different cases of 'epic'."""
        # Setup
        epic_type = NetworkJiraIssueType(id="10", name="EPIC", subtask=False)

        # Execute
        result = prepare_epic_name(epic_type, "My Epic")

        # Assert
        assert result == "My Epic"


class TestFindSubtaskIssueType:
    """Tests for find_subtask_issue_type function."""

    def test_finds_subtask_type(self):
        """Should find first subtask issue type."""
        # Setup
        mock_client = Mock()
        issue_types = [
            NetworkJiraIssueType(id="1", name="Bug", subtask=False),
            NetworkJiraIssueType(id="5", name="Sub-task", subtask=True),
            NetworkJiraIssueType(id="2", name="Story", subtask=False),
        ]
        mock_client.get_issue_types.return_value = ClientSuccess(data=issue_types)

        # Execute
        result = find_subtask_issue_type(mock_client, "PROJ")

        # Assert
        assert isinstance(result, ClientSuccess)
        assert result.data.id == "5"
        assert result.data.name == "Sub-task"
        assert result.data.subtask is True

    def test_no_subtask_type_found(self):
        """Should return error when no subtask type exists."""
        # Setup
        mock_client = Mock()
        issue_types = [
            NetworkJiraIssueType(id="1", name="Bug", subtask=False),
            NetworkJiraIssueType(id="2", name="Story", subtask=False),
        ]
        mock_client.get_issue_types.return_value = ClientSuccess(data=issue_types)

        # Execute
        result = find_subtask_issue_type(mock_client, "PROJ")

        # Assert
        assert isinstance(result, ClientError)
        assert "No subtask issue type found" in result.error_message
        assert result.error_code == "NO_SUBTASK_TYPE"

    def test_propagates_api_error(self):
        """Should propagate API error from get_issue_types."""
        # Setup
        mock_client = Mock()
        mock_client.get_issue_types.return_value = ClientError(
            error_message="API Error", error_code="API_ERROR"
        )

        # Execute
        result = find_subtask_issue_type(mock_client, "PROJ")

        # Assert
        assert isinstance(result, ClientError)
        assert result.error_message == "API Error"
