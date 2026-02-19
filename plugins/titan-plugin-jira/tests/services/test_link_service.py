"""
Unit tests for LinkService
"""

import pytest
from titan_cli.core.result import ClientSuccess, ClientError
from titan_plugin_jira.clients.services.link_service import LinkService
from titan_plugin_jira.exceptions import JiraAPIError


@pytest.fixture
def service(mock_jira_network):
    return LinkService(mock_jira_network)


@pytest.mark.unit
class TestLinkServiceLinkIssues:
    """Test LinkService.link_issues()"""

    def test_links_two_issues_with_default_type(self, service, mock_jira_network):
        """Test creates link with default 'Relates' type"""
        mock_jira_network.make_request.return_value = {}

        result = service.link_issues("PROJ-1", "PROJ-2")

        assert isinstance(result, ClientSuccess)
        mock_jira_network.make_request.assert_called_once_with(
            "POST", "issueLink",
            json={
                "type": {"name": "Relates"},
                "inwardIssue": {"key": "PROJ-1"},
                "outwardIssue": {"key": "PROJ-2"}
            }
        )

    def test_links_with_custom_type(self, service, mock_jira_network):
        """Test creates link with custom link type"""
        mock_jira_network.make_request.return_value = {}

        result = service.link_issues("PROJ-1", "PROJ-2", link_type="Blocks")

        assert isinstance(result, ClientSuccess)
        payload = mock_jira_network.make_request.call_args.kwargs["json"]
        assert payload["type"]["name"] == "Blocks"

    def test_api_error_returns_client_error(self, service, mock_jira_network):
        """Test API error returns ClientError"""
        mock_jira_network.make_request.side_effect = JiraAPIError("issue not found", status_code=404)

        result = service.link_issues("PROJ-1", "MISSING-99")

        assert isinstance(result, ClientError)
        assert result.error_code == "LINK_ERROR"


@pytest.mark.unit
class TestLinkServiceAddRemoteLink:
    """Test LinkService.add_remote_link()"""

    def test_adds_remote_link_and_returns_id(self, service, mock_jira_network):
        """Test adds remote link and returns the created link ID"""
        mock_jira_network.make_request.return_value = {"id": "99999"}

        result = service.add_remote_link(
            "PROJ-1",
            "https://github.com/org/repo/pull/42",
            "PR #42: Add feature"
        )

        assert isinstance(result, ClientSuccess)
        assert result.data == "99999"

    def test_calls_correct_endpoint(self, service, mock_jira_network):
        """Test calls remotelink endpoint for the correct issue"""
        mock_jira_network.make_request.return_value = {"id": "1"}

        service.add_remote_link("TEST-123", "https://example.com", "Example")

        call_args = mock_jira_network.make_request.call_args
        assert call_args.args[1] == "issue/TEST-123/remotelink"

    def test_payload_includes_url_and_title(self, service, mock_jira_network):
        """Test payload correctly includes url and title"""
        mock_jira_network.make_request.return_value = {"id": "1"}

        service.add_remote_link("PROJ-1", "https://github.com/pr/1", "My PR", relationship="closes")

        payload = mock_jira_network.make_request.call_args.kwargs["json"]
        assert payload["object"]["url"] == "https://github.com/pr/1"
        assert payload["object"]["title"] == "My PR"
        assert payload["relationship"] == "closes"

    def test_api_error_returns_client_error(self, service, mock_jira_network):
        """Test API error returns ClientError"""
        mock_jira_network.make_request.side_effect = JiraAPIError("forbidden", status_code=403)

        result = service.add_remote_link("PROJ-1", "https://example.com", "Title")

        assert isinstance(result, ClientError)
        assert result.error_code == "ADD_REMOTE_LINK_ERROR"
