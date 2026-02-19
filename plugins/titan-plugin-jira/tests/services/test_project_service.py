"""
Unit tests for ProjectService
"""

import pytest
from titan_cli.core.result import ClientSuccess, ClientError
from titan_plugin_jira.clients.services.project_service import ProjectService
from titan_plugin_jira.exceptions import JiraAPIError


@pytest.fixture
def service(mock_jira_network):
    return ProjectService(mock_jira_network)


@pytest.fixture
def sample_project_api_data():
    """Sample project response from Jira API"""
    return {
        "id": "10000",
        "key": "TEST",
        "name": "Test Project",
        "description": "A test project",
        "projectTypeKey": "software",
        "self": "https://test.atlassian.net/rest/api/2/project/10000",
        "lead": {
            "displayName": "Project Lead",
            "accountId": "lead-123",
            "emailAddress": "lead@example.com",
            "avatarUrls": {"48x48": "https://avatar.url"},
            "active": True
        },
        "issueTypes": [
            {
                "id": "10004",
                "name": "Bug",
                "description": "A bug",
                "subtask": False,
                "iconUrl": "https://icon.url/bug"
            },
            {
                "id": "10001",
                "name": "Story",
                "description": "A story",
                "subtask": False,
                "iconUrl": "https://icon.url/story"
            }
        ]
    }


@pytest.mark.unit
class TestProjectServiceGetProject:
    """Test ProjectService.get_project()"""

    def test_returns_ui_project(self, service, mock_jira_network, sample_project_api_data):
        """Test maps API response to UIJiraProject"""
        mock_jira_network.make_request.return_value = sample_project_api_data

        result = service.get_project("TEST")

        assert isinstance(result, ClientSuccess)
        assert result.data.key == "TEST"
        assert result.data.name == "Test Project"
        mock_jira_network.make_request.assert_called_once_with("GET", "project/TEST")

    def test_project_has_issue_types(self, service, mock_jira_network, sample_project_api_data):
        """Test mapped project includes issue type names"""
        mock_jira_network.make_request.return_value = sample_project_api_data

        result = service.get_project("TEST")

        assert "Bug" in result.data.issue_types
        assert "Story" in result.data.issue_types

    def test_project_has_lead_name(self, service, mock_jira_network, sample_project_api_data):
        """Test mapped project includes lead display name"""
        mock_jira_network.make_request.return_value = sample_project_api_data

        result = service.get_project("TEST")

        assert result.data.lead_name == "Project Lead"

    def test_not_found_returns_not_found_error_code(self, service, mock_jira_network):
        """Test 404 API error returns NOT_FOUND error code"""
        mock_jira_network.make_request.side_effect = JiraAPIError("not found", status_code=404)

        result = service.get_project("MISSING")

        assert isinstance(result, ClientError)
        assert result.error_code == "NOT_FOUND"

    def test_other_api_error_returns_api_error_code(self, service, mock_jira_network):
        """Test non-404 API error returns API_ERROR code"""
        mock_jira_network.make_request.side_effect = JiraAPIError("server error", status_code=500)

        result = service.get_project("TEST")

        assert isinstance(result, ClientError)
        assert result.error_code == "API_ERROR"


@pytest.mark.unit
class TestProjectServiceListProjects:
    """Test ProjectService.list_projects()"""

    def test_returns_list_of_ui_projects(self, service, mock_jira_network, sample_project_api_data):
        """Test maps list API response to list of UIJiraProject"""
        mock_jira_network.make_request.return_value = [
            sample_project_api_data,
            {**sample_project_api_data, "id": "10001", "key": "OTHER", "name": "Other Project"}
        ]

        result = service.list_projects()

        assert isinstance(result, ClientSuccess)
        assert len(result.data) == 2
        keys = [p.key for p in result.data]
        assert "TEST" in keys
        assert "OTHER" in keys

    def test_empty_list_returns_empty(self, service, mock_jira_network):
        """Test empty list from API returns empty list"""
        mock_jira_network.make_request.return_value = []

        result = service.list_projects()

        assert isinstance(result, ClientSuccess)
        assert result.data == []

    def test_api_error_returns_client_error(self, service, mock_jira_network):
        """Test API error returns ClientError"""
        mock_jira_network.make_request.side_effect = JiraAPIError("forbidden", status_code=403)

        result = service.list_projects()

        assert isinstance(result, ClientError)
        assert result.error_code == "LIST_ERROR"
