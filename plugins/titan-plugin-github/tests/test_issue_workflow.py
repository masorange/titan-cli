import pytest
from unittest.mock import MagicMock, patch
from titan_cli.engine.context import WorkflowContext
from titan_cli.engine.results import Success, Error
from titan_cli.core.secrets import SecretManager
from titan_plugin_github.steps.github_prompt_steps import prompt_for_issue_body_step, prompt_for_self_assign_step
from titan_plugin_github.steps.issue_steps import ai_suggest_issue_title_and_body_step, create_issue_steps
from titan_plugin_github.steps.preview_step import preview_and_confirm_issue_step
from titan_plugin_github.models.network.rest import RESTIssue, RESTUser

@pytest.fixture
def mock_secret_manager():
    return MagicMock(spec=SecretManager)

def test_prompt_for_issue_body_step(mock_secret_manager):
    # Arrange
    ctx = WorkflowContext(secrets=mock_secret_manager, data={})
    ctx.textual = MagicMock()
    ctx.textual.ask_multiline.return_value = "Test issue body"

    # Act
    result = prompt_for_issue_body_step(ctx)
    ctx.data.update(result.metadata)

    # Assert
    assert isinstance(result, Success)
    assert ctx.get("issue_body") == "Test issue body"
    ctx.textual.begin_step.assert_called_once()
    ctx.textual.end_step.assert_called_once_with("success")

@patch("titan_plugin_github.steps.issue_steps.IssueGeneratorAgent")
def test_ai_suggest_issue_title_and_body(MockIssueGeneratorAgent, mock_secret_manager):
    # Arrange
    mock_issue_generator = MockIssueGeneratorAgent.return_value
    mock_issue_generator.generate_issue.return_value = {
        "title": "feat: Test Feature",
        "body": "Test Body",
        "category": "feature",
        "labels": ["feature"],
        "template_used": True,
        "tokens_used": 450,
        "complexity": "moderate"
    }
    ctx = WorkflowContext(secrets=mock_secret_manager, data={"issue_body": "Test issue body"})
    ctx.ai = MagicMock()
    ctx.textual = MagicMock()
    # Mock ai_content_review_flow to return (choice, title, body)
    ctx.textual.ai_content_review_flow.return_value = ("use", "feat: Test Feature", "Test Body")

    # Act
    result = ai_suggest_issue_title_and_body_step(ctx)

    # Assert
    assert isinstance(result, Success)
    assert ctx.get("issue_title") == "feat: Test Feature"
    assert ctx.get("issue_body") == "Test Body"
    assert ctx.get("issue_category") == "feature"
    assert ctx.get("labels") == ["feature"]
    assert "feature" in result.message

def test_ai_suggest_issue_title_and_body_bug_category(mock_secret_manager):
    # Arrange
    with patch("titan_plugin_github.steps.issue_steps.IssueGeneratorAgent") as MockIssueGeneratorAgent:
        mock_issue_generator = MockIssueGeneratorAgent.return_value
        mock_issue_generator.generate_issue.return_value = {
            "title": "fix: Test Bug Fix",
            "body": "Bug description",
            "category": "bug",
            "labels": ["bug"],
            "template_used": True,
            "tokens_used": 380,
            "complexity": "simple"
        }
        ctx = WorkflowContext(secrets=mock_secret_manager, data={"issue_body": "Something is broken"})
        ctx.ai = MagicMock()
        ctx.textual = MagicMock()
        # Mock ai_content_review_flow to return (choice, title, body)
        ctx.textual.ai_content_review_flow.return_value = ("use", "fix: Test Bug Fix", "Bug description")

        # Act
        result = ai_suggest_issue_title_and_body_step(ctx)

        # Assert
        assert isinstance(result, Success)
        assert ctx.get("issue_category") == "bug"
        assert ctx.get("labels") == ["bug"]

def test_ai_suggest_issue_title_and_body_without_template(mock_secret_manager):
    # Arrange
    with patch("titan_plugin_github.steps.issue_steps.IssueGeneratorAgent") as MockIssueGeneratorAgent:
        mock_issue_generator = MockIssueGeneratorAgent.return_value
        mock_issue_generator.generate_issue.return_value = {
            "title": "chore: Update dependencies",
            "body": "Chore description",
            "category": "chore",
            "labels": ["chore", "maintenance"],
            "template_used": False,  # No template found
            "tokens_used": 320,
            "complexity": "simple"
        }
        ctx = WorkflowContext(secrets=mock_secret_manager, data={"issue_body": "Update deps"})
        ctx.ai = MagicMock()
        ctx.textual = MagicMock()
        # Mock ai_content_review_flow to return (choice, title, body)
        ctx.textual.ai_content_review_flow.return_value = ("use", "chore: Update dependencies", "Chore description")

        # Act
        result = ai_suggest_issue_title_and_body_step(ctx)

        # Assert
        assert isinstance(result, Success)
        assert ctx.get("issue_category") == "chore"
        assert ctx.get("labels") == ["chore", "maintenance"]

def test_preview_and_confirm_issue_step(mock_secret_manager):
    # Arrange
    ctx = WorkflowContext(secrets=mock_secret_manager, data={"issue_title": "Test Title", "issue_body": "Test Body"})
    ctx.textual = MagicMock()
    ctx.textual.ask_confirm.return_value = True

    # Act
    result = preview_and_confirm_issue_step(ctx)

    # Assert
    assert isinstance(result, Success)

def test_prompt_for_self_assign_step(mock_secret_manager):
    # Arrange
    ctx = WorkflowContext(secrets=mock_secret_manager, data={})
    ctx.github = MagicMock()
    ctx.textual = MagicMock()
    ctx.github.get_current_user.return_value = "testuser"
    ctx.textual.ask_confirm.return_value = True

    # Act
    result = prompt_for_self_assign_step(ctx)
    if result.metadata:
        ctx.data.update(result.metadata)

    # Assert
    assert isinstance(result, Success)
    assert ctx.get("assignees") == ["testuser"]

@patch("titan_plugin_github.clients.github_client.GitHubClient")
def test_create_issue_step(MockGitHubClient, mock_secret_manager):
    # Arrange
    mock_github_client = MockGitHubClient()
    mock_issue = RESTIssue(
        number=1,
        title="Test RESTIssue",
        body="This is a test issue",
        state="OPEN",
        author=RESTUser(login="testuser"),
        labels=[],
    )
    mock_github_client.create_issue.return_value = mock_issue
    mock_github_client.list_labels.return_value = ["bug", "feature", "improvement"]  # Mock available labels

    ctx = WorkflowContext(secrets=mock_secret_manager, data={"issue_title": "Test Title", "issue_body": "Test Body", "assignees": ["testuser"], "labels": ["bug"]})
    ctx.github = mock_github_client
    ctx.textual = MagicMock()

    # Act
    result = create_issue_steps(ctx)
    if result.metadata:
        ctx.data.update(result.metadata)

    # Assert
    assert isinstance(result, Success)
    assert result.message == "Successfully created issue #1"
    assert ctx.get("issue") == mock_issue
    mock_github_client.create_issue.assert_called_once_with(
        title="Test Title",
        body="Test Body",
        assignees=["testuser"],
        labels=["bug"],
    )

def test_create_issue_with_auto_assigned_labels(mock_secret_manager):
    # Arrange
    with patch("titan_plugin_github.clients.github_client.GitHubClient") as MockGitHubClient:
        mock_github_client = MockGitHubClient()
        mock_issue = RESTIssue(
            number=2,
            title="feat: New Feature",
            body="Feature description",
            state="OPEN",
            author=RESTUser(login="testuser"),
            labels=["feature"],
        )
        mock_github_client.create_issue.return_value = mock_issue
        mock_github_client.list_labels.return_value = ["bug", "feature", "improvement"]  # Mock available labels

        # Labels auto-assigned by AI categorization
        ctx = WorkflowContext(
            secrets=mock_secret_manager,
            data={
                "issue_title": "feat: New Feature",
                "issue_body": "Feature description",
                "assignees": [],
                "labels": ["feature"]  # Auto-assigned
            }
        )
        ctx.github = mock_github_client
        ctx.textual = MagicMock()

        # Act
        result = create_issue_steps(ctx)
        if result.metadata:
            ctx.data.update(result.metadata)

        # Assert
        assert isinstance(result, Success)
        mock_github_client.create_issue.assert_called_once_with(
            title="feat: New Feature",
            body="Feature description",
            assignees=[],
            labels=["feature"],
        )

# ============================================================================
# JSON Parsing Tests
# ============================================================================

def test_parse_ai_response_with_json_format():
    """Test that JSON parsing works correctly"""
    from titan_plugin_github.agents.issue_generator import IssueGeneratorAgent
    from unittest.mock import MagicMock

    agent = IssueGeneratorAgent(MagicMock())

    # Test JSON format
    json_response = '''
    {
      "category": "bug",
      "title": "fix(auth): resolve login timeout issue",
      "body": "## Description\\nUsers experiencing timeout errors during login"
    }
    '''

    category, title, body = agent._parse_ai_response(json_response)

    assert category == "bug"
    assert title == "fix(auth): resolve login timeout issue"
    assert "Users experiencing timeout" in body

def test_parse_ai_response_with_fallback_regex():
    """Test that regex fallback works when JSON parsing fails"""
    from titan_plugin_github.agents.issue_generator import IssueGeneratorAgent
    from unittest.mock import MagicMock

    agent = IssueGeneratorAgent(MagicMock())

    # Test old format (should use regex fallback)
    old_format_response = '''
    CATEGORY: feature
    TITLE: feat(api): add new endpoint
    DESCRIPTION:
    ## Summary
    New API endpoint for user management
    '''

    category, title, body = agent._parse_ai_response(old_format_response)

    assert category == "feature"
    assert title == "feat(api): add new endpoint"
    assert "Summary" in body

def test_parse_ai_response_with_user_category_text():
    """Test that JSON parsing avoids conflicts with user text containing 'CATEGORY:'"""
    from titan_plugin_github.agents.issue_generator import IssueGeneratorAgent
    from unittest.mock import MagicMock

    agent = IssueGeneratorAgent(MagicMock())

    # User description contains "CATEGORY:" but JSON should parse correctly
    response_with_conflict = '''
    {
      "category": "bug",
      "title": "fix(docs): update CATEGORY: field documentation",
      "body": "The CATEGORY: field in the config is confusing users"
    }
    '''

    category, title, body = agent._parse_ai_response(response_with_conflict)

    assert category == "bug"
    assert "CATEGORY: field" in title
    assert "CATEGORY: field in the config" in body

# ============================================================================
# Error Scenario Tests
# ============================================================================

@patch("titan_plugin_github.steps.issue_steps.IssueGeneratorAgent")
def test_ai_suggest_issue_when_ai_client_fails(MockIssueGeneratorAgent, mock_secret_manager):
    """Test behavior when AI client raises exception"""
    # Arrange
    mock_issue_generator = MockIssueGeneratorAgent.return_value
    mock_issue_generator.generate_issue.side_effect = Exception("API Error")

    ctx = WorkflowContext(secrets=mock_secret_manager, data={"issue_body": "Test issue body"})
    ctx.ai = MagicMock()
    ctx.textual = MagicMock()

    # Act
    result = ai_suggest_issue_title_and_body_step(ctx)

    # Assert
    assert isinstance(result, Error)
    assert "Failed to generate issue" in result.message
    assert "API Error" in result.message

@patch("titan_plugin_github.steps.issue_steps.IssueGeneratorAgent")
def test_ai_suggest_issue_with_malformed_response(MockIssueGeneratorAgent, mock_secret_manager):
    """Test behavior when AI returns malformed response missing required keys"""
    # Arrange
    mock_issue_generator = MockIssueGeneratorAgent.return_value
    # Malformed response - missing required keys like "title" or "body"
    mock_issue_generator.generate_issue.return_value = {
        "category": "bug"
        # Missing: title, body, labels
    }

    ctx = WorkflowContext(secrets=mock_secret_manager, data={"issue_body": "Test issue body"})
    ctx.ai = MagicMock()
    ctx.textual = MagicMock()

    # Act
    result = ai_suggest_issue_title_and_body_step(ctx)

    # Assert
    assert isinstance(result, Error)
    assert "Failed to generate issue" in result.message

@patch("titan_plugin_github.clients.github_client.GitHubClient")
def test_create_issue_with_invalid_labels(MockGitHubClient, mock_secret_manager):
    """Test behavior when labels don't exist in repository - they should be filtered out"""
    # Arrange
    mock_github_client = MockGitHubClient()
    mock_github_client.list_labels.return_value = ["bug", "feature", "improvement"]
    mock_issue = RESTIssue(
        number=3,
        title="Test Title",
        body="Test Body",
        state="OPEN",
        author=RESTUser(login="testuser"),
        labels=[],  # No labels since invalid ones were filtered
    )
    mock_github_client.create_issue.return_value = mock_issue

    ctx = WorkflowContext(
        secrets=mock_secret_manager,
        data={
            "issue_title": "Test Title",
            "issue_body": "Test Body",
            "assignees": [],
            "labels": ["invalid-label", "nonexistent"]  # Labels that don't exist
        }
    )
    ctx.github = mock_github_client
    ctx.textual = MagicMock()

    # Act
    result = create_issue_steps(ctx)

    # Assert
    # The step should succeed but filter out invalid labels
    assert isinstance(result, Success)
    # Verify create_issue was called with empty labels (invalid ones filtered)
    mock_github_client.create_issue.assert_called_once_with(
        title="Test Title",
        body="Test Body",
        assignees=[],
        labels=[],  # Invalid labels filtered out
    )

@patch("titan_plugin_github.clients.github_client.GitHubClient")
def test_create_issue_when_github_api_fails(MockGitHubClient, mock_secret_manager):
    """Test behavior when GitHub API fails to create issue"""
    # Arrange
    mock_github_client = MockGitHubClient()
    mock_github_client.list_labels.return_value = ["bug", "feature"]
    mock_github_client.create_issue.side_effect = Exception("GitHub API Error")

    ctx = WorkflowContext(
        secrets=mock_secret_manager,
        data={
            "issue_title": "Test Title",
            "issue_body": "Test Body",
            "assignees": [],
            "labels": ["bug"]
        }
    )
    ctx.github = mock_github_client
    ctx.textual = MagicMock()

    # Act
    result = create_issue_steps(ctx)

    # Assert
    assert isinstance(result, Error)
    assert "Failed to create issue" in result.message
    assert "GitHub API Error" in result.message
