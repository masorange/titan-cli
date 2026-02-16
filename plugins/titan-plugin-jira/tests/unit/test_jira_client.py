"""
Unit tests for JiraClient (Facade)

Tests that the client correctly delegates to services and provides a clean public API.
"""

import pytest
from unittest.mock import Mock, patch
from titan_cli.core.result import ClientSuccess, ClientError
from titan_plugin_jira.clients import JiraClient
from titan_plugin_jira.models import NetworkJiraIssueType


@pytest.fixture
def mock_network():
    """Mock JiraNetwork"""
    with patch('titan_plugin_jira.clients.jira_client.JiraNetwork') as mock:
        yield mock.return_value


@pytest.fixture
def jira_client(mock_network):
    """Create a JiraClient instance with mocked network"""
    return JiraClient(
        base_url="https://test.atlassian.net",
        email="test@example.com",
        api_token="test-token",
        project_key="TEST"
    )


def test_client_initialization():
    """Test that client initializes correctly"""
    client = JiraClient(
        base_url="https://test.atlassian.net",
        email="test@example.com",
        api_token="test-token",
        project_key="TEST",
        timeout=60
    )

    assert client.project_key == "TEST"
    assert client._network is not None
    assert client._issue_service is not None
    assert client._project_service is not None
    assert client._comment_service is not None
    assert client._transition_service is not None
    assert client._metadata_service is not None
    assert client._link_service is not None


def test_get_issue_delegates_to_service(jira_client, sample_ui_issue):
    """Test that get_issue delegates to IssueService"""
    # Mock the service method
    jira_client._issue_service.get_issue = Mock(
        return_value=ClientSuccess(data=sample_ui_issue, message="Success")
    )

    # Call client method
    result = jira_client.get_issue("TEST-123")

    # Assertions
    assert isinstance(result, ClientSuccess)
    assert result.data.key == "TEST-123"
    jira_client._issue_service.get_issue.assert_called_once_with("TEST-123", None)


def test_get_issue_with_expand(jira_client, sample_ui_issue):
    """Test get_issue with expand parameter"""
    jira_client._issue_service.get_issue = Mock(
        return_value=ClientSuccess(data=sample_ui_issue, message="Success")
    )

    result = jira_client.get_issue("TEST-123", expand=["changelog"])

    assert isinstance(result, ClientSuccess)
    jira_client._issue_service.get_issue.assert_called_once_with("TEST-123", ["changelog"])


def test_search_issues_delegates_to_service(jira_client, sample_ui_issue):
    """Test that search_issues delegates to IssueService"""
    jira_client._issue_service.search_issues = Mock(
        return_value=ClientSuccess(data=[sample_ui_issue], message="Found 1 issues")
    )

    result = jira_client.search_issues(jql="project=TEST", max_results=50)

    assert isinstance(result, ClientSuccess)
    assert len(result.data) == 1
    jira_client._issue_service.search_issues.assert_called_once_with("project=TEST", 50, None)


def test_get_project_uses_default_key(jira_client, sample_ui_project):
    """Test that get_project uses default project_key if not provided"""
    jira_client._project_service.get_project = Mock(
        return_value=ClientSuccess(data=sample_ui_project, message="Success")
    )

    result = jira_client.get_project()

    assert isinstance(result, ClientSuccess)
    assert result.data.key == "TEST"
    jira_client._project_service.get_project.assert_called_once_with("TEST")


def test_get_project_with_custom_key(jira_client, sample_ui_project):
    """Test that get_project accepts custom key"""
    jira_client._project_service.get_project = Mock(
        return_value=ClientSuccess(data=sample_ui_project, message="Success")
    )

    result = jira_client.get_project("CUSTOM")

    assert isinstance(result, ClientSuccess)
    jira_client._project_service.get_project.assert_called_once_with("CUSTOM")


def test_get_project_no_default_key():
    """Test that get_project returns error when no key provided"""
    client = JiraClient(
        base_url="https://test.atlassian.net",
        email="test@example.com",
        api_token="token",
        project_key=None  # No default
    )

    result = client.get_project()

    assert isinstance(result, ClientError)
    assert result.error_code == "MISSING_PROJECT_KEY"


def test_create_issue_gets_issue_type_id(jira_client, sample_ui_issue):
    """Test that create_issue resolves issue type name to ID"""
    # Mock get_issue_types to return issue types
    issue_types = [
        NetworkJiraIssueType(id="10004", name="Bug", subtask=False),
        NetworkJiraIssueType(id="10001", name="Story", subtask=False)
    ]
    jira_client._metadata_service.get_issue_types = Mock(
        return_value=ClientSuccess(data=issue_types, message="Success")
    )

    # Mock create_issue
    jira_client._issue_service.create_issue = Mock(
        return_value=ClientSuccess(data=sample_ui_issue, message="Created")
    )

    # Call client method with issue_type name
    result = jira_client.create_issue(
        issue_type="Bug",
        summary="New bug"
    )

    # Assertions
    assert isinstance(result, ClientSuccess)

    # Verify it got issue types
    jira_client._metadata_service.get_issue_types.assert_called_once_with("TEST")

    # Verify it called create with the ID
    call_args = jira_client._issue_service.create_issue.call_args
    assert call_args[1]["issue_type_id"] == "10004"  # Bug's ID


def test_create_issue_invalid_type(jira_client):
    """Test create_issue with invalid issue type name"""
    # Mock get_issue_types
    issue_types = [
        NetworkJiraIssueType(id="10004", name="Bug", subtask=False)
    ]
    jira_client._metadata_service.get_issue_types = Mock(
        return_value=ClientSuccess(data=issue_types, message="Success")
    )

    # Call with invalid type
    result = jira_client.create_issue(
        issue_type="InvalidType",
        summary="New issue"
    )

    # Should return error
    assert isinstance(result, ClientError)
    assert result.error_code == "INVALID_ISSUE_TYPE"
    assert "InvalidType" in result.error_message
    assert "Bug" in result.error_message  # Should show available types


def test_create_subtask_finds_subtask_type(jira_client, sample_ui_issue):
    """Test that create_subtask finds the subtask issue type"""
    # Mock get_issue_types
    issue_types = [
        NetworkJiraIssueType(id="10004", name="Bug", subtask=False),
        NetworkJiraIssueType(id="10005", name="Sub-task", subtask=True)
    ]
    jira_client._metadata_service.get_issue_types = Mock(
        return_value=ClientSuccess(data=issue_types, message="Success")
    )

    # Mock create_subtask
    jira_client._issue_service.create_subtask = Mock(
        return_value=ClientSuccess(data=sample_ui_issue, message="Created")
    )

    # Call client method
    result = jira_client.create_subtask(
        parent_key="TEST-100",
        summary="New subtask"
    )

    # Assertions
    assert isinstance(result, ClientSuccess)

    # Verify it called create with the subtask type ID
    call_args = jira_client._issue_service.create_subtask.call_args
    assert call_args[1]["subtask_type_id"] == "10005"


def test_list_statuses_uses_default_project(jira_client):
    """Test that list_statuses uses default project_key"""
    jira_client._metadata_service.list_statuses = Mock(
        return_value=ClientSuccess(data=[], message="Success")
    )

    result = jira_client.list_statuses()

    assert isinstance(result, ClientSuccess)
    jira_client._metadata_service.list_statuses.assert_called_once_with("TEST")


def test_list_statuses_with_custom_project(jira_client):
    """Test list_statuses with custom project"""
    jira_client._metadata_service.list_statuses = Mock(
        return_value=ClientSuccess(data=[], message="Success")
    )

    result = jira_client.list_statuses("CUSTOM")

    assert isinstance(result, ClientSuccess)
    jira_client._metadata_service.list_statuses.assert_called_once_with("CUSTOM")


def test_get_issue_types_uses_default_project(jira_client):
    """Test that get_issue_types uses default project_key"""
    jira_client._metadata_service.get_issue_types = Mock(
        return_value=ClientSuccess(data=[], message="Success")
    )

    result = jira_client.get_issue_types()

    assert isinstance(result, ClientSuccess)
    jira_client._metadata_service.get_issue_types.assert_called_once_with("TEST")


def test_list_project_versions_uses_default_project(jira_client):
    """Test that list_project_versions uses default project_key"""
    jira_client._metadata_service.list_project_versions = Mock(
        return_value=ClientSuccess(data=[], message="Success")
    )

    result = jira_client.list_project_versions()

    assert isinstance(result, ClientSuccess)
    jira_client._metadata_service.list_project_versions.assert_called_once_with("TEST")


def test_list_project_versions_no_default_key():
    """Test list_project_versions returns error when no key provided"""
    client = JiraClient(
        base_url="https://test.atlassian.net",
        email="test@example.com",
        api_token="token",
        project_key=None
    )

    result = client.list_project_versions()

    assert isinstance(result, ClientError)
    assert result.error_code == "MISSING_PROJECT_KEY"


def test_get_comments_delegates(jira_client):
    """Test that get_comments delegates to CommentService"""
    jira_client._comment_service.get_comments = Mock(
        return_value=ClientSuccess(data=[], message="Success")
    )

    result = jira_client.get_comments("TEST-123")

    assert isinstance(result, ClientSuccess)
    jira_client._comment_service.get_comments.assert_called_once_with("TEST-123")


def test_add_comment_delegates(jira_client):
    """Test that add_comment delegates to CommentService"""
    jira_client._comment_service.add_comment = Mock(
        return_value=ClientSuccess(data=Mock(), message="Success")
    )

    result = jira_client.add_comment("TEST-123", "Test comment")

    assert isinstance(result, ClientSuccess)
    jira_client._comment_service.add_comment.assert_called_once_with("TEST-123", "Test comment")


def test_get_transitions_delegates(jira_client):
    """Test that get_transitions delegates to TransitionService"""
    jira_client._transition_service.get_transitions = Mock(
        return_value=ClientSuccess(data=[], message="Success")
    )

    result = jira_client.get_transitions("TEST-123")

    assert isinstance(result, ClientSuccess)
    jira_client._transition_service.get_transitions.assert_called_once_with("TEST-123")


def test_transition_issue_delegates(jira_client):
    """Test that transition_issue delegates to TransitionService"""
    jira_client._transition_service.transition_issue = Mock(
        return_value=ClientSuccess(data=None, message="Success")
    )

    result = jira_client.transition_issue("TEST-123", "Done", comment="Completed")

    assert isinstance(result, ClientSuccess)
    jira_client._transition_service.transition_issue.assert_called_once_with(
        "TEST-123", "Done", "Completed"
    )


def test_link_issue_delegates(jira_client):
    """Test that link_issue delegates to LinkService"""
    jira_client._link_service.link_issues = Mock(
        return_value=ClientSuccess(data=None, message="Success")
    )

    result = jira_client.link_issue("TEST-123", "TEST-124", "Relates")

    assert isinstance(result, ClientSuccess)
    jira_client._link_service.link_issues.assert_called_once_with("TEST-123", "TEST-124", "Relates")


def test_add_remote_link_delegates(jira_client):
    """Test that add_remote_link delegates to LinkService"""
    jira_client._link_service.add_remote_link = Mock(
        return_value=ClientSuccess(data="10001", message="Success")
    )

    result = jira_client.add_remote_link("TEST-123", "https://github.com/pr/1", "PR #1")

    assert isinstance(result, ClientSuccess)
    jira_client._link_service.add_remote_link.assert_called_once_with(
        "TEST-123", "https://github.com/pr/1", "PR #1", "relates to"
    )
