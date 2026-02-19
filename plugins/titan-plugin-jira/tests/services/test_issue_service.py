"""
Unit tests for IssueService

Tests the Service layer which transforms Network models to UI models
and wraps results in ClientResult.
"""

import pytest
from unittest.mock import Mock
from titan_cli.core.result import ClientSuccess, ClientError
from titan_plugin_jira.clients.services import IssueService
from titan_plugin_jira.exceptions import JiraAPIError


@pytest.fixture
def mock_network():
    """Create a mock JiraNetwork"""
    return Mock()


@pytest.fixture
def issue_service(mock_network):
    """Create an IssueService instance"""
    return IssueService(mock_network)


@pytest.fixture
def sample_api_issue_response():
    """Sample issue response from Jira API"""
    return {
        "id": "10123",
        "key": "TEST-123",
        "self": "https://test.atlassian.net/rest/api/2/issue/10123",
        "fields": {
            "summary": "Fix login bug",
            "description": "Users cannot login with valid credentials",
            "status": {
                "id": "10001",
                "name": "In Progress",
                "description": "Work in progress",
                "statusCategory": {
                    "id": "4",
                    "key": "indeterminate",
                    "name": "In Progress",
                    "colorName": "yellow"
                }
            },
            "issuetype": {
                "id": "10004",
                "name": "Bug",
                "description": "A software bug",
                "subtask": False,
                "iconUrl": "https://test.atlassian.net/images/icons/bug.png"
            },
            "priority": {
                "id": "2",
                "name": "High",
                "iconUrl": "https://test.atlassian.net/images/icons/priority_high.svg"
            },
            "assignee": {
                "displayName": "John Doe",
                "accountId": "557058:f58131cb-b67d-43c7-b30d-6b58d40bd077",
                "emailAddress": "john.doe@example.com",
                "avatarUrls": {"48x48": "https://avatar.url"},
                "active": True
            },
            "reporter": {
                "displayName": "Jane Doe",
                "accountId": "557058:a1b2c3d4-e5f6-g7h8-i9j0-k1l2m3n4o5p6",
                "emailAddress": "jane.doe@example.com",
                "avatarUrls": {"48x48": "https://avatar.url"},
                "active": True
            },
            "created": "2025-01-01T12:00:00.000+0000",
            "updated": "2025-01-02T12:00:00.000+0000",
            "labels": ["backend", "authentication"],
            "components": [],
            "fixVersions": []
        }
    }


def test_get_issue_success(issue_service, mock_network, sample_api_issue_response):
    """Test successful issue retrieval"""
    # Setup mock
    mock_network.make_request.return_value = sample_api_issue_response

    # Call service
    result = issue_service.get_issue("TEST-123")

    # Assertions
    assert isinstance(result, ClientSuccess)
    assert result.data.key == "TEST-123"
    assert result.data.summary == "Fix login bug"
    assert result.data.status == "In Progress"
    assert result.data.issue_type == "Bug"
    assert result.data.priority == "High"
    assert result.data.assignee == "John Doe"
    assert result.data.assignee_email == "john.doe@example.com"
    assert result.data.reporter == "Jane Doe"
    assert "backend" in result.data.labels
    assert "authentication" in result.data.labels

    # Verify network was called correctly
    mock_network.make_request.assert_called_once_with(
        "GET",
        "issue/TEST-123",
        params={}
    )


def test_get_issue_with_expand(issue_service, mock_network, sample_api_issue_response):
    """Test issue retrieval with expand parameter"""
    # Setup mock
    mock_network.make_request.return_value = sample_api_issue_response

    # Call service with expand
    result = issue_service.get_issue("TEST-123", expand=["changelog", "renderedFields"])

    # Assertions
    assert isinstance(result, ClientSuccess)

    # Verify expand was passed correctly
    mock_network.make_request.assert_called_once_with(
        "GET",
        "issue/TEST-123",
        params={"expand": "changelog,renderedFields"}
    )


def test_get_issue_not_found(issue_service, mock_network):
    """Test issue retrieval when issue doesn't exist (404)"""
    # Setup mock to raise 404
    mock_network.make_request.side_effect = JiraAPIError(
        "Issue not found",
        status_code=404
    )

    # Call service
    result = issue_service.get_issue("NOTFOUND-999")

    # Assertions
    assert isinstance(result, ClientError)
    assert result.error_code == "ISSUE_NOT_FOUND"
    assert "not found" in result.error_message.lower()


def test_get_issue_api_error(issue_service, mock_network):
    """Test issue retrieval when API returns error"""
    # Setup mock to raise API error
    mock_network.make_request.side_effect = JiraAPIError(
        "Internal server error",
        status_code=500
    )

    # Call service
    result = issue_service.get_issue("TEST-123")

    # Assertions
    assert isinstance(result, ClientError)
    assert result.error_code == "API_ERROR"
    assert "TEST-123" in result.error_message


def test_search_issues_success(issue_service, mock_network, sample_api_issue_response):
    """Test successful issue search"""
    # Setup mock
    mock_network.make_request.return_value = {
        "issues": [sample_api_issue_response],
        "total": 1,
        "maxResults": 50
    }

    # Call service
    result = issue_service.search_issues(
        jql="project=TEST AND status='In Progress'",
        max_results=50
    )

    # Assertions
    assert isinstance(result, ClientSuccess)
    assert len(result.data) == 1
    assert result.data[0].key == "TEST-123"
    assert result.data[0].summary == "Fix login bug"
    assert "Found 1 issues" in result.message

    # Verify network was called correctly
    mock_network.make_request.assert_called_once()
    call_args = mock_network.make_request.call_args
    assert call_args[0][0] == "POST"
    assert call_args[0][1] == "search"
    assert call_args[1]["json"]["jql"] == "project=TEST AND status='In Progress'"
    assert call_args[1]["json"]["maxResults"] == 50


def test_search_issues_empty_results(issue_service, mock_network):
    """Test search that returns no issues"""
    # Setup mock
    mock_network.make_request.return_value = {
        "issues": [],
        "total": 0,
        "maxResults": 50
    }

    # Call service
    result = issue_service.search_issues(jql="project=EMPTY")

    # Assertions
    assert isinstance(result, ClientSuccess)
    assert len(result.data) == 0
    assert "Found 0 issues" in result.message


def test_search_issues_with_custom_fields(issue_service, mock_network, sample_api_issue_response):
    """Test search with custom field selection"""
    # Setup mock
    mock_network.make_request.return_value = {
        "issues": [sample_api_issue_response],
        "total": 1
    }

    # Call service with custom fields
    result = issue_service.search_issues(
        jql="project=TEST",
        max_results=25,
        fields=["summary", "status", "assignee"]
    )

    # Assertions
    assert isinstance(result, ClientSuccess)

    # Verify fields were passed
    call_args = mock_network.make_request.call_args
    assert call_args[1]["json"]["fields"] == ["summary", "status", "assignee"]
    assert call_args[1]["json"]["maxResults"] == 25


def test_search_issues_api_error(issue_service, mock_network):
    """Test search when API returns error"""
    # Setup mock to raise error
    mock_network.make_request.side_effect = JiraAPIError("Invalid JQL")

    # Call service
    result = issue_service.search_issues(jql="invalid jql syntax")

    # Assertions
    assert isinstance(result, ClientError)
    assert result.error_code == "SEARCH_ERROR"


def test_create_issue_success(issue_service, mock_network, sample_api_issue_response):
    """Test successful issue creation"""
    # Setup mocks
    mock_network.make_request.side_effect = [
        {"id": "10124", "key": "TEST-124"},  # POST response
        sample_api_issue_response  # GET response
    ]

    # Call service
    result = issue_service.create_issue(
        project_key="TEST",
        issue_type_id="10004",
        summary="New bug",
        description="Description here"
    )

    # Assertions
    assert isinstance(result, ClientSuccess)
    assert result.data.key == "TEST-123"  # From get_issue call

    # Verify network calls
    assert mock_network.make_request.call_count == 2
    # First call: POST to create
    first_call = mock_network.make_request.call_args_list[0]
    assert first_call[0][0] == "POST"
    assert first_call[0][1] == "issue"
    # Second call: GET to fetch created issue
    second_call = mock_network.make_request.call_args_list[1]
    assert second_call[0][0] == "GET"


def test_create_issue_with_optional_fields(issue_service, mock_network, sample_api_issue_response):
    """Test issue creation with optional fields"""
    # Setup mocks
    mock_network.make_request.side_effect = [
        {"id": "10124", "key": "TEST-124"},
        sample_api_issue_response
    ]

    # Call service with all optional fields
    result = issue_service.create_issue(
        project_key="TEST",
        issue_type_id="10004",
        summary="New issue",
        description="Description",
        assignee="john.doe",
        labels=["backend", "urgent"],
        priority="High"
    )

    # Assertions
    assert isinstance(result, ClientSuccess)

    # Verify payload included optional fields
    create_call = mock_network.make_request.call_args_list[0]
    payload = create_call[1]["json"]
    assert payload["fields"]["assignee"] == {"name": "john.doe"}
    assert payload["fields"]["labels"] == ["backend", "urgent"]
    assert payload["fields"]["priority"] == {"name": "High"}


def test_create_issue_api_error(issue_service, mock_network):
    """Test issue creation when API returns error"""
    # Setup mock to raise error
    mock_network.make_request.side_effect = JiraAPIError("Permission denied")

    # Call service
    result = issue_service.create_issue(
        project_key="TEST",
        issue_type_id="10004",
        summary="New issue"
    )

    # Assertions
    assert isinstance(result, ClientError)
    assert result.error_code == "CREATE_ISSUE_ERROR"


def test_create_subtask_success(issue_service, mock_network, sample_api_issue_response):
    """Test successful subtask creation"""
    # Setup mocks
    mock_network.make_request.side_effect = [
        {"id": "10125", "key": "TEST-125"},
        sample_api_issue_response
    ]

    # Call service
    result = issue_service.create_subtask(
        parent_key="TEST-100",
        project_key="TEST",
        subtask_type_id="10005",
        summary="Subtask summary",
        description="Subtask description"
    )

    # Assertions
    assert isinstance(result, ClientSuccess)

    # Verify parent was set in payload
    create_call = mock_network.make_request.call_args_list[0]
    payload = create_call[1]["json"]
    assert payload["fields"]["parent"] == {"key": "TEST-100"}
    assert payload["fields"]["issuetype"] == {"id": "10005"}


def test_ui_model_has_formatted_fields(issue_service, mock_network, sample_api_issue_response):
    """Test that UI model has pre-formatted fields"""
    # Setup mock
    mock_network.make_request.return_value = sample_api_issue_response

    # Call service
    result = issue_service.get_issue("TEST-123")

    # Verify UI model has formatted fields
    ui_issue = result.data
    assert hasattr(ui_issue, 'status_icon')
    assert hasattr(ui_issue, 'issue_type_icon')
    assert hasattr(ui_issue, 'priority_icon')
    assert hasattr(ui_issue, 'formatted_created_at')
    assert hasattr(ui_issue, 'formatted_updated_at')

    # Icons should be present
    assert ui_issue.status_icon in ["🔵", "🟡", "🟢", "⚪"]  # Valid status icons
    assert ui_issue.priority_icon in ["🔴", "🟠", "🟡", "🟢", "🔵", "⚪"]  # Valid priority icons (🟠 for High)
