"""
Unit tests for workflow steps (new architecture)

Tests that steps correctly use ClientResult pattern and handle UI models.
"""

from titan_cli.engine import Success, Error
from titan_cli.core.result import ClientSuccess, ClientError
from titan_plugin_jira.steps.get_issue_step import get_issue_step
from titan_plugin_jira.steps.search_jql_step import search_jql_step
from titan_plugin_jira.steps.list_versions_step import list_versions_step


def test_get_issue_step_success(mock_workflow_context, mock_jira_client_new, sample_ui_issue):
    """Test get_issue_step with successful result"""
    # Setup
    mock_workflow_context.jira = mock_jira_client_new
    mock_workflow_context.data["jira_issue_key"] = "TEST-123"

    # Mock client to return success
    mock_jira_client_new.get_issue.return_value = ClientSuccess(
        data=sample_ui_issue,
        message="Issue retrieved"
    )

    # Execute step
    result = get_issue_step(mock_workflow_context)

    # Assertions
    assert isinstance(result, Success)
    assert "jira_issue" in result.metadata
    assert result.metadata["jira_issue"].key == "TEST-123"

    # Verify client was called
    mock_jira_client_new.get_issue.assert_called_once()


def test_get_issue_step_not_found(mock_workflow_context, mock_jira_client_new):
    """Test get_issue_step when issue not found"""
    # Setup
    mock_workflow_context.jira = mock_jira_client_new
    mock_workflow_context.data["jira_issue_key"] = "NOTFOUND-999"

    # Mock client to return error
    mock_jira_client_new.get_issue.return_value = ClientError(
        error_message="Issue not found",
        error_code="ISSUE_NOT_FOUND"
    )

    # Execute step
    result = get_issue_step(mock_workflow_context)

    # Assertions
    assert isinstance(result, Error)
    assert "not found" in result.message.lower()


def test_get_issue_step_no_key(mock_workflow_context, mock_jira_client_new):
    """Test get_issue_step when no issue key provided"""
    # Setup
    mock_workflow_context.jira = mock_jira_client_new
    # No issue_key in data

    # Execute step
    result = get_issue_step(mock_workflow_context)

    # Assertions
    assert isinstance(result, Error)
    assert "required" in result.message.lower()


def test_get_issue_step_no_jira_client(mock_workflow_context):
    """Test get_issue_step when Jira client not available"""
    # Setup - no jira client
    mock_workflow_context.jira = None
    mock_workflow_context.data["jira_issue_key"] = "TEST-123"

    # Execute step
    result = get_issue_step(mock_workflow_context)

    # Assertions
    assert isinstance(result, Error)


def test_search_jql_step_success(mock_workflow_context, mock_jira_client_new, sample_ui_issue):
    """Test search_jql_step with successful results"""
    # Setup
    mock_workflow_context.jira = mock_jira_client_new
    mock_workflow_context.data["jql"] = "project=TEST"

    # Mock client to return success
    mock_jira_client_new.search_issues.return_value = ClientSuccess(
        data=[sample_ui_issue],
        message="Found 1 issues"
    )

    # Execute step
    result = search_jql_step(mock_workflow_context)

    # Assertions
    assert isinstance(result, Success)
    assert "jira_issues" in result.metadata
    assert len(result.metadata["jira_issues"]) == 1
    assert result.metadata["jira_issue_count"] == 1

    # Verify client was called
    mock_jira_client_new.search_issues.assert_called_once()


def test_search_jql_step_no_results(mock_workflow_context, mock_jira_client_new):
    """Test search_jql_step with no results"""
    # Setup
    mock_workflow_context.jira = mock_jira_client_new
    mock_workflow_context.data["jql"] = "project=EMPTY"

    # Mock client to return empty list
    mock_jira_client_new.search_issues.return_value = ClientSuccess(
        data=[],
        message="Found 0 issues"
    )

    # Execute step
    result = search_jql_step(mock_workflow_context)

    # Assertions
    assert isinstance(result, Success)
    assert result.metadata["jira_issue_count"] == 0


def test_search_jql_step_error(mock_workflow_context, mock_jira_client_new):
    """Test search_jql_step when search fails"""
    # Setup
    mock_workflow_context.jira = mock_jira_client_new
    mock_workflow_context.data["jql"] = "invalid jql"

    # Mock client to return error
    mock_jira_client_new.search_issues.return_value = ClientError(
        error_message="Invalid JQL",
        error_code="SEARCH_ERROR"
    )

    # Execute step
    result = search_jql_step(mock_workflow_context)

    # Assertions
    assert isinstance(result, Error)


def test_search_jql_step_no_jql(mock_workflow_context, mock_jira_client_new):
    """Test search_jql_step when no JQL provided"""
    # Setup
    mock_workflow_context.jira = mock_jira_client_new
    # No jql in data

    # Execute step
    result = search_jql_step(mock_workflow_context)

    # Assertions
    assert isinstance(result, Error)
    assert "required" in result.message.lower()


def test_list_versions_step_success(mock_workflow_context, mock_jira_client_new):
    """Test list_versions_step with successful results"""
    # Setup
    mock_workflow_context.jira = mock_jira_client_new
    mock_workflow_context.data["project_key"] = "TEST"

    # Mock client to return versions
    versions = [
        {"id": "10200", "name": "v1.0.0", "released": False, "releaseDate": None},
        {"id": "10201", "name": "v2.0.0", "released": False, "releaseDate": "2025-06-01"}
    ]
    mock_jira_client_new.list_project_versions.return_value = ClientSuccess(
        data=versions,
        message="Found 2 versions"
    )

    # Execute step
    result = list_versions_step(mock_workflow_context)

    # Assertions
    assert isinstance(result, Success)
    assert "versions" in result.metadata
    assert "versions_full" in result.metadata
    assert len(result.metadata["versions"]) == 2


def test_list_versions_step_uses_default_project(mock_workflow_context, mock_jira_client_new):
    """Test list_versions_step uses default project from client"""
    # Setup - no project_key in data, should use client default
    mock_workflow_context.jira = mock_jira_client_new
    mock_jira_client_new.project_key = "DEFAULT"

    # Mock client
    mock_jira_client_new.list_project_versions.return_value = ClientSuccess(
        data=[],
        message="Found 0 versions"
    )

    # Execute step
    result = list_versions_step(mock_workflow_context)

    # Should use default project
    assert isinstance(result, Success)


def test_list_versions_step_no_versions(mock_workflow_context, mock_jira_client_new):
    """Test list_versions_step with no versions"""
    # Setup
    mock_workflow_context.jira = mock_jira_client_new
    mock_workflow_context.data["project_key"] = "TEST"

    # Mock client to return empty list
    mock_jira_client_new.list_project_versions.return_value = ClientSuccess(
        data=[],
        message="Found 0 versions"
    )

    # Execute step
    result = list_versions_step(mock_workflow_context)

    # Assertions
    assert isinstance(result, Success)
    assert result.metadata["versions"] == []


def test_list_versions_step_error(mock_workflow_context, mock_jira_client_new):
    """Test list_versions_step when API returns error"""
    # Setup
    mock_workflow_context.jira = mock_jira_client_new
    mock_workflow_context.data["project_key"] = "TEST"

    # Mock client to return error
    mock_jira_client_new.list_project_versions.return_value = ClientError(
        error_message="Project not found",
        error_code="NOT_FOUND"
    )

    # Execute step
    result = list_versions_step(mock_workflow_context)

    # Assertions
    assert isinstance(result, Error)
