"""
Pytest configuration and shared fixtures for JIRA plugin tests
"""

import pytest
from unittest.mock import Mock, MagicMock


# ==================== NEW ARCHITECTURE FIXTURES ====================


@pytest.fixture
def sample_network_issue():
    """Create a sample NetworkJiraIssue (raw API response model)"""
    from titan_plugin_jira.models import (
        NetworkJiraIssue,
        NetworkJiraFields,
        NetworkJiraStatus,
        NetworkJiraStatusCategory,
        NetworkJiraIssueType,
        NetworkJiraPriority,
        NetworkJiraUser,
    )

    status_category = NetworkJiraStatusCategory(
        id="3",
        name="In Progress",
        key="indeterminate",
        colorName="yellow"
    )

    status = NetworkJiraStatus(
        id="10001",
        name="In Progress",
        description="Work in progress",
        statusCategory=status_category
    )

    issue_type = NetworkJiraIssueType(
        id="10004",
        name="Bug",
        description="A software bug",
        subtask=False,
        iconUrl="https://test.atlassian.net/images/icons/bug.png"
    )

    priority = NetworkJiraPriority(
        id="2",
        name="High",
        iconUrl="https://test.atlassian.net/images/icons/priority_high.svg"
    )

    assignee = NetworkJiraUser(
        displayName="John Doe",
        accountId="557058:f58131cb-b67d-43c7-b30d-6b58d40bd077",
        emailAddress="john.doe@example.com",
        avatarUrls={"48x48": "https://avatar.url"},
        active=True
    )

    reporter = NetworkJiraUser(
        displayName="Jane Doe",
        accountId="557058:a1b2c3d4-e5f6-g7h8-i9j0-k1l2m3n4o5p6",
        emailAddress="jane.doe@example.com",
        avatarUrls={"48x48": "https://avatar.url"},
        active=True
    )

    fields = NetworkJiraFields(
        summary="Sample test issue",
        description="This is a test issue description",
        status=status,
        issuetype=issue_type,
        assignee=assignee,
        reporter=reporter,
        priority=priority,
        created="2025-01-01T12:00:00.000+0000",
        updated="2025-01-02T12:00:00.000+0000",
        labels=["test", "bug"],
        components=None,
        fixVersions=None,
        parent=None,
        subtasks=None
    )

    return NetworkJiraIssue(
        key="TEST-123",
        id="10123",
        fields=fields,
        self="https://test.atlassian.net/rest/api/2/issue/10123"
    )


@pytest.fixture
def sample_ui_issue():
    """Create a sample UIJiraIssue (pre-formatted for display)"""
    from titan_plugin_jira.models import UIJiraIssue

    return UIJiraIssue(
        key="TEST-123",
        id="10123",
        summary="Sample test issue",
        description="This is a test issue description",
        status="In Progress",
        status_icon="🔵",
        status_category="In Progress",
        issue_type="Bug",
        issue_type_icon="🐛",
        assignee="John Doe",
        assignee_email="john.doe@example.com",
        reporter="Jane Doe",
        priority="High",
        priority_icon="🔴",
        formatted_created_at="01/01/2025 12:00:00",
        formatted_updated_at="02/01/2025 12:00:00",
        labels=["test", "bug"],
        components=[],
        fix_versions=[],
        is_subtask=False,
        parent_key=None,
        subtask_count=0
    )


@pytest.fixture
def sample_network_project():
    """Create a sample NetworkJiraProject"""
    from titan_plugin_jira.models import NetworkJiraProject, NetworkJiraUser, NetworkJiraIssueType

    lead = NetworkJiraUser(
        displayName="Project Lead",
        accountId="557058:lead123",
        emailAddress="lead@example.com",
        avatarUrls={"48x48": "https://avatar.url"},
        active=True
    )

    issue_types = [
        NetworkJiraIssueType(
            id="10004",
            name="Bug",
            description="A software bug",
            subtask=False,
            iconUrl="https://test.atlassian.net/images/icons/bug.png"
        ),
        NetworkJiraIssueType(
            id="10001",
            name="Story",
            description="A user story",
            subtask=False,
            iconUrl="https://test.atlassian.net/images/icons/story.png"
        )
    ]

    return NetworkJiraProject(
        id="10000",
        key="TEST",
        name="Test Project",
        description="A test project",
        projectTypeKey="software",
        lead=lead,
        issueTypes=issue_types,
        self="https://test.atlassian.net/rest/api/2/project/10000"
    )


@pytest.fixture
def sample_ui_project():
    """Create a sample UIJiraProject"""
    from titan_plugin_jira.models import UIJiraProject

    return UIJiraProject(
        id="10000",
        key="TEST",
        name="Test Project",
        description="A test project",
        project_type="software",
        lead_name="Project Lead",
        issue_types=["Bug", "Story"]
    )


@pytest.fixture
def mock_jira_network():
    """Create a mock JiraNetwork for testing services"""
    network = Mock()
    network.base_url = "https://test.atlassian.net"
    network.timeout = 30
    return network


@pytest.fixture
def mock_jira_client_new():
    """Create a mock JIRA client (new architecture) for testing steps"""
    from titan_cli.core.result import ClientSuccess
    from titan_plugin_jira.models import UIJiraIssue

    client = Mock()
    client.base_url = "https://test.atlassian.net"
    client.email = "test@example.com"
    client.project_key = "TEST"
    client.timeout = 30

    # Mock methods to return ClientSuccess by default
    sample_issue = UIJiraIssue(
        key="TEST-123",
        id="10123",
        summary="Sample test issue",
        description="This is a test issue description",
        status="In Progress",
        status_icon="🔵",
        status_category="In Progress",
        issue_type="Bug",
        issue_type_icon="🐛",
        assignee="John Doe",
        assignee_email="john.doe@example.com",
        reporter="Jane Doe",
        priority="High",
        priority_icon="🔴",
        formatted_created_at="01/01/2025 12:00:00",
        formatted_updated_at="02/01/2025 12:00:00",
        labels=["test", "bug"],
        components=[],
        fix_versions=[],
        is_subtask=False,
        parent_key=None,
        subtask_count=0
    )

    client.get_issue.return_value = ClientSuccess(
        data=sample_issue,
        message="Issue retrieved successfully"
    )

    client.search_issues.return_value = ClientSuccess(
        data=[sample_issue],
        message="Found 1 issues"
    )

    return client


@pytest.fixture
def client_success():
    """Factory for creating ClientSuccess instances"""
    from titan_cli.core.result import ClientSuccess

    def _create(data, message="Success"):
        return ClientSuccess(data=data, message=message)

    return _create


@pytest.fixture
def client_error():
    """Factory for creating ClientError instances"""
    from titan_cli.core.result import ClientError

    def _create(error_message, error_code=None):
        return ClientError(
            error_message=error_message,
            error_code=error_code
        )

    return _create


# ==================== LEGACY FIXTURES (for old tests) ====================


@pytest.fixture
def mock_jira_client():
    """Create a mock JIRA client for testing (LEGACY - for old tests)"""
    client = Mock()
    client.base_url = "https://test.atlassian.net"
    client.email = "test@example.com"
    client.project_key = "TEST"
    client.timeout = 30
    return client


@pytest.fixture
def mock_workflow_context():
    """Create a mock WorkflowContext for testing steps"""
    ctx = Mock()
    ctx.views = None
    ctx.ui = None
    ctx.data = {}
    ctx.current_step = 1
    ctx.total_steps = 1
    ctx.plugin_manager = None
    ctx.get = lambda key, default=None: ctx.data.get(key, default)
    ctx.set = lambda key, value: ctx.data.update({key: value})

    # Mock textual UI context
    ctx.textual = MagicMock()
    ctx.textual.mount = MagicMock()
    ctx.textual.text = MagicMock()
    ctx.textual.bold_text = MagicMock()
    ctx.textual.dim_text = MagicMock()
    ctx.textual.primary_text = MagicMock()
    ctx.textual.success_text = MagicMock()
    ctx.textual.error_text = MagicMock()
    ctx.textual.markdown = MagicMock()
    ctx.textual.panel = MagicMock()
    ctx.textual.ask_confirm = MagicMock(return_value=True)
    ctx.textual.ask_text = MagicMock(return_value="1")
    ctx.textual.begin_step = MagicMock()
    ctx.textual.end_step = MagicMock()

    # Mock loading as a context manager
    loading_mock = MagicMock()
    loading_mock.__enter__ = MagicMock(return_value=loading_mock)
    loading_mock.__exit__ = MagicMock(return_value=None)
    ctx.textual.loading = MagicMock(return_value=loading_mock)

    return ctx


@pytest.fixture
def sample_statuses():
    """Create sample JIRA statuses for testing"""
    return [
        {
            "id": "1",
            "name": "To Do",
            "statusCategory": {"name": "To Do"}
        },
        {
            "id": "2",
            "name": "In Progress",
            "statusCategory": {"name": "In Progress"}
        },
        {
            "id": "3",
            "name": "Done",
            "statusCategory": {"name": "Done"}
        }
    ]


def pytest_configure(config):
    """Configure pytest with custom markers"""
    config.addinivalue_line(
        "markers",
        "integration: marks tests as integration tests (require real JIRA or mock server)"
    )
    config.addinivalue_line(
        "markers",
        "unit: marks tests as unit tests (use mocks, no external dependencies)"
    )
