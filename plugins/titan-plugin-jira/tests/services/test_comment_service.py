"""
Unit tests for CommentService
"""

import pytest
from titan_cli.core.result import ClientSuccess, ClientError
from titan_plugin_jira.clients.services.comment_service import CommentService
from titan_plugin_jira.exceptions import JiraAPIError


@pytest.fixture
def service(mock_jira_network):
    return CommentService(mock_jira_network)


@pytest.fixture
def sample_comment_data():
    """Sample comment from Jira API"""
    return {
        "id": "12345",
        "author": {
            "displayName": "John Doe",
            "accountId": "user-abc123",
            "emailAddress": "john@example.com",
            "avatarUrls": {"48x48": "https://avatar.url"},
            "active": True
        },
        "body": {
            "type": "doc",
            "version": 1,
            "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Great work!"}]}]
        },
        "created": "2025-01-01T12:00:00.000+0000",
        "updated": "2025-01-01T12:00:00.000+0000",
        "self": "https://test.atlassian.net/rest/api/2/issue/TEST-123/comment/12345"
    }


@pytest.mark.unit
class TestCommentServiceGetComments:
    """Test CommentService.get_comments()"""

    def test_returns_ui_comment_list(self, service, mock_jira_network, sample_comment_data):
        """Test maps API response to list of UIJiraComment"""
        mock_jira_network.make_request.return_value = {
            "comments": [sample_comment_data, sample_comment_data]
        }

        result = service.get_comments("TEST-123")

        assert isinstance(result, ClientSuccess)
        assert len(result.data) == 2
        mock_jira_network.make_request.assert_called_once_with(
            "GET", "issue/TEST-123/comment"
        )

    def test_no_comments_returns_empty_list(self, service, mock_jira_network):
        """Test issue with no comments returns empty list"""
        mock_jira_network.make_request.return_value = {"comments": []}

        result = service.get_comments("TEST-123")

        assert isinstance(result, ClientSuccess)
        assert result.data == []

    def test_comment_has_author_info(self, service, mock_jira_network, sample_comment_data):
        """Test mapped comments carry author display name"""
        mock_jira_network.make_request.return_value = {"comments": [sample_comment_data]}

        result = service.get_comments("TEST-123")

        comment = result.data[0]
        assert comment.author_name == "John Doe"

    def test_api_error_returns_client_error(self, service, mock_jira_network):
        """Test API error returns ClientError"""
        mock_jira_network.make_request.side_effect = JiraAPIError("not found", status_code=404)

        result = service.get_comments("MISSING-999")

        assert isinstance(result, ClientError)
        assert result.error_code == "GET_COMMENTS_ERROR"


@pytest.mark.unit
class TestCommentServiceAddComment:
    """Test CommentService.add_comment()"""

    def test_posts_adf_payload(self, service, mock_jira_network, sample_comment_data):
        """Test sends comment in ADF format"""
        mock_jira_network.make_request.return_value = sample_comment_data

        service.add_comment("TEST-123", "This looks good!")

        call_args = mock_jira_network.make_request.call_args
        assert call_args.args[0] == "POST"
        assert call_args.args[1] == "issue/TEST-123/comment"
        payload = call_args.kwargs["json"]
        assert payload["body"]["type"] == "doc"

    def test_returns_ui_comment(self, service, mock_jira_network, sample_comment_data):
        """Test returns the created comment as UIJiraComment"""
        mock_jira_network.make_request.return_value = sample_comment_data

        result = service.add_comment("TEST-123", "LGTM!")

        assert isinstance(result, ClientSuccess)
        assert result.data.id == "12345"
        assert result.data.author_name == "John Doe"

    def test_api_error_returns_client_error(self, service, mock_jira_network):
        """Test API error returns ClientError"""
        mock_jira_network.make_request.side_effect = JiraAPIError("forbidden", status_code=403)

        result = service.add_comment("TEST-123", "Comment text")

        assert isinstance(result, ClientError)
        assert result.error_code == "ADD_COMMENT_ERROR"
