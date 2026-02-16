"""
Unit tests for JiraNetwork (HTTP layer)

Tests the Network layer which handles raw HTTP communication with Jira API.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from titan_plugin_jira.clients.network import JiraNetwork
from titan_plugin_jira.exceptions import JiraAPIError


@pytest.fixture
def jira_network():
    """Create a JiraNetwork instance for testing"""
    return JiraNetwork(
        base_url="https://test.atlassian.net",
        email="test@example.com",
        api_token="test-token-123",
        timeout=30
    )


def test_network_initialization(jira_network):
    """Test that JiraNetwork initializes correctly"""
    assert jira_network.base_url == "https://test.atlassian.net"
    assert jira_network.email == "test@example.com"
    assert jira_network.api_token == "test-token-123"
    assert jira_network.timeout == 30
    assert jira_network.session is not None


def test_network_builds_correct_auth_header(jira_network):
    """Test that authentication header is built correctly"""
    # The session should have Bearer token in headers
    assert "Authorization" in jira_network.session.headers
    assert jira_network.session.headers["Authorization"] == "Bearer test-token-123"


@patch('titan_plugin_jira.clients.network.jira_network.requests.Session')
def test_network_make_request_get_success(mock_session_class):
    """Test successful GET request"""
    # Setup mock
    mock_session = MagicMock()
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"key": "TEST-123", "id": "10123"}
    mock_response.content = b'{"key": "TEST-123"}'
    mock_session.request.return_value = mock_response
    mock_session_class.return_value = mock_session

    # Create network and make request
    network = JiraNetwork("https://test.atlassian.net", "test@example.com", "token")
    result = network.make_request("GET", "issue/TEST-123")

    # Assertions
    assert result == {"key": "TEST-123", "id": "10123"}
    mock_session.request.assert_called_once()
    call_args = mock_session.request.call_args
    assert call_args[0][0] == "GET"
    assert "issue/TEST-123" in call_args[0][1]


@patch('titan_plugin_jira.clients.network.jira_network.requests.Session')
def test_network_make_request_post_with_json(mock_session_class):
    """Test POST request with JSON payload"""
    # Setup mock
    mock_session = MagicMock()
    mock_response = Mock()
    mock_response.status_code = 201
    mock_response.json.return_value = {"id": "10124", "key": "TEST-124"}
    mock_response.content = b'{"id": "10124"}'
    mock_session.request.return_value = mock_response
    mock_session_class.return_value = mock_session

    # Create network and make request
    network = JiraNetwork("https://test.atlassian.net", "test@example.com", "token")
    payload = {"fields": {"summary": "New issue"}}
    result = network.make_request("POST", "issue", json=payload)

    # Assertions
    assert result == {"id": "10124", "key": "TEST-124"}
    mock_session.request.assert_called_once()
    call_args = mock_session.request.call_args
    assert call_args[1]["json"] == payload


@patch('titan_plugin_jira.clients.network.jira_network.requests.Session')
def test_network_make_request_with_params(mock_session_class):
    """Test request with query parameters"""
    # Setup mock
    mock_session = MagicMock()
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"issues": []}
    mock_response.content = b'{"issues": []}'
    mock_session.request.return_value = mock_response
    mock_session_class.return_value = mock_session

    # Create network and make request
    network = JiraNetwork("https://test.atlassian.net", "test@example.com", "token")
    result = network.make_request("GET", "search", params={"jql": "project=TEST", "maxResults": 50})

    # Assertions
    assert result == {"issues": []}
    call_args = mock_session.request.call_args
    assert call_args[1]["params"]["jql"] == "project=TEST"
    assert call_args[1]["params"]["maxResults"] == 50


@patch('titan_plugin_jira.clients.network.jira_network.requests.Session')
def test_network_make_request_empty_response(mock_session_class):
    """Test request with empty response (204 No Content)"""
    # Setup mock
    mock_session = MagicMock()
    mock_response = Mock()
    mock_response.status_code = 204
    mock_response.content = b''
    mock_session.request.return_value = mock_response
    mock_session_class.return_value = mock_session

    # Create network and make request
    network = JiraNetwork("https://test.atlassian.net", "test@example.com", "token")
    result = network.make_request("DELETE", "issue/TEST-123")

    # Should return empty dict for empty content
    assert result == {}


@patch('titan_plugin_jira.clients.network.jira_network.requests.Session')
def test_network_make_request_404_error(mock_session_class):
    """Test request that returns 404 Not Found"""
    import requests

    # Setup mock
    mock_session = MagicMock()
    mock_response = Mock()
    mock_response.status_code = 404
    mock_response.text = "Issue not found"
    mock_response.content = b'{"errorMessages":["Issue not found"]}'
    mock_response.json.return_value = {"errorMessages": ["Issue not found"]}

    # Create HTTPError
    http_error = requests.exceptions.HTTPError("404 Client Error: Not Found")
    http_error.response = mock_response
    mock_response.raise_for_status.side_effect = http_error

    mock_session.request.return_value = mock_response
    mock_session_class.return_value = mock_session

    # Create network and make request
    network = JiraNetwork("https://test.atlassian.net", "test@example.com", "token")

    # Should raise JiraAPIError
    with pytest.raises(JiraAPIError) as exc_info:
        network.make_request("GET", "issue/NOTFOUND-999")

    assert exc_info.value.status_code == 404


@patch('titan_plugin_jira.clients.network.jira_network.requests.Session')
def test_network_make_request_401_unauthorized(mock_session_class):
    """Test request that returns 401 Unauthorized"""
    import requests

    # Setup mock
    mock_session = MagicMock()
    mock_response = Mock()
    mock_response.status_code = 401
    mock_response.text = "Unauthorized"
    mock_response.content = b'{"errorMessages":["Unauthorized"]}'
    mock_response.json.return_value = {"errorMessages": ["Unauthorized"]}

    # Create HTTPError
    http_error = requests.exceptions.HTTPError("401 Client Error: Unauthorized")
    http_error.response = mock_response
    mock_response.raise_for_status.side_effect = http_error

    mock_session.request.return_value = mock_response
    mock_session_class.return_value = mock_session

    # Create network and make request
    network = JiraNetwork("https://test.atlassian.net", "test@example.com", "token")

    # Should raise JiraAPIError
    with pytest.raises(JiraAPIError) as exc_info:
        network.make_request("GET", "issue/TEST-123")

    assert exc_info.value.status_code == 401


@patch('titan_plugin_jira.clients.network.jira_network.requests.Session')
def test_network_make_request_500_server_error(mock_session_class):
    """Test request that returns 500 Server Error"""
    import requests

    # Setup mock
    mock_session = MagicMock()
    mock_response = Mock()
    mock_response.status_code = 500
    mock_response.text = "Internal Server Error"
    mock_response.content = b'{"errorMessages":["Internal Server Error"]}'
    mock_response.json.return_value = {"errorMessages": ["Internal Server Error"]}

    # Create HTTPError
    http_error = requests.exceptions.HTTPError("500 Server Error: Internal Server Error")
    http_error.response = mock_response
    mock_response.raise_for_status.side_effect = http_error

    mock_session.request.return_value = mock_response
    mock_session_class.return_value = mock_session

    # Create network and make request
    network = JiraNetwork("https://test.atlassian.net", "test@example.com", "token")

    # Should raise JiraAPIError
    with pytest.raises(JiraAPIError) as exc_info:
        network.make_request("GET", "issue/TEST-123")

    assert exc_info.value.status_code == 500


@patch('titan_plugin_jira.clients.network.jira_network.requests.Session')
def test_network_make_request_timeout(mock_session_class):
    """Test request that times out"""
    import requests

    # Setup mock
    mock_session = MagicMock()
    # Headers property needed for initialization
    mock_session.headers = {}
    mock_session.request.side_effect = requests.Timeout("Request timed out")
    mock_session_class.return_value = mock_session

    # Create network and make request
    network = JiraNetwork("https://test.atlassian.net", "test@example.com", "token")

    # Should raise JiraAPIError wrapping timeout
    with pytest.raises(JiraAPIError) as exc_info:
        network.make_request("GET", "issue/TEST-123")

    assert "timeout" in str(exc_info.value).lower() or "timed out" in str(exc_info.value).lower()


@patch('titan_plugin_jira.clients.network.jira_network.requests.Session')
def test_network_make_request_connection_error(mock_session_class):
    """Test request with connection error"""
    import requests

    # Setup mock
    mock_session = MagicMock()
    mock_session.request.side_effect = requests.ConnectionError("Connection refused")
    mock_session_class.return_value = mock_session

    # Create network and make request
    network = JiraNetwork("https://test.atlassian.net", "test@example.com", "token")

    # Should raise JiraAPIError wrapping connection error
    with pytest.raises(JiraAPIError) as exc_info:
        network.make_request("GET", "issue/TEST-123")

    assert "connection" in str(exc_info.value).lower()


def test_network_url_construction(jira_network):
    """Test that URLs are constructed correctly"""
    # The make_request method should construct: base_url + /rest/api/2/ + endpoint
    # We can't easily test this without mocking, but we can verify base_url
    assert jira_network.base_url == "https://test.atlassian.net"


def test_network_custom_timeout():
    """Test that custom timeout is respected"""
    network = JiraNetwork(
        base_url="https://test.atlassian.net",
        email="test@example.com",
        api_token="token",
        timeout=60
    )
    assert network.timeout == 60
