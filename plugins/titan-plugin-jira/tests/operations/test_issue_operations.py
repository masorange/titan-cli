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
)
from titan_plugin_jira.models import UITransition


class TestFindReadyToDevTransition:
    """Tests for find_ready_to_dev_transition function."""

    def test_finds_ready_to_dev_transition(self):
        """Should find 'Ready to Dev' transition when it exists."""
        # Setup
        mock_client = Mock()
        transitions = [
            UITransition(
                id="11",
                name="Start Progress",
                to_status="In Progress",
                has_screen=False,
            ),
            UITransition(
                id="21", name="Ready to Dev", to_status="Ready to Dev", has_screen=False
            ),
            UITransition(id="31", name="Done", to_status="Done", has_screen=False),
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
            UITransition(
                id="21",
                name="Ready for Development",
                to_status="Ready for Dev",
                has_screen=False,
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
            UITransition(
                id="21", name="READY TO DEV", to_status="Ready to Dev", has_screen=False
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
            UITransition(
                id="11",
                name="Start Progress",
                to_status="In Progress",
                has_screen=False,
            ),
            UITransition(id="31", name="Done", to_status="Done", has_screen=False),
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
            UITransition(
                id="11", name="Ready to Start", to_status="Ready", has_screen=False
            ),
            UITransition(
                id="21", name="In Development", to_status="In Dev", has_screen=False
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
        transition = UITransition(
            id="21", name="Ready to Dev", to_status="Ready to Dev", has_screen=False
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
                UITransition(
                    id="11",
                    name="Start Progress",
                    to_status="In Progress",
                    has_screen=False,
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
        transition = UITransition(
            id="21", name="Ready to Dev", to_status="Ready to Dev", has_screen=False
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
        transition = UITransition(
            id="21",
            name="READY FOR DEVELOPMENT",
            to_status="Ready for Dev",
            has_screen=False,
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
