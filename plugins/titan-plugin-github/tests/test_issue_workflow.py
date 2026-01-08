import pytest
from unittest.mock import MagicMock, patch
from titan_cli.engine.context import WorkflowContext
from titan_cli.engine.results import Success
from titan_cli.core.secrets import SecretManager
from titan_plugin_github.steps.github_prompt_steps import prompt_for_issue_body_step, prompt_for_self_assign_step, prompt_for_labels_step
from titan_plugin_github.steps.template_steps import find_issue_template_step
from titan_plugin_github.steps.issue_steps import ai_suggest_issue_title_and_body, create_issue
from titan_plugin_github.steps.preview_steps import preview_and_confirm_issue_step
from titan_plugin_github.models import Issue, User

@pytest.fixture
def mock_secret_manager():
    return MagicMock(spec=SecretManager)

def test_prompt_for_issue_body_step(mock_secret_manager):
    # Arrange
    ctx = WorkflowContext(secrets=mock_secret_manager, data={})
    ctx.views = MagicMock()
    ctx.views.prompts.ask_multiline.return_value = "Test issue body"

    # Act
    result = prompt_for_issue_body_step(ctx)
    ctx.data.update(result.metadata)

    # Assert
    assert isinstance(result, Success)
    assert ctx.get("issue_body") == "Test issue body"

def test_find_issue_template_step(tmp_path, mock_secret_manager):
    # Arrange
    ctx = WorkflowContext(secrets=mock_secret_manager, data={})
    github_dir = tmp_path / ".github"
    github_dir.mkdir()
    template_file = github_dir / "ISSUE_TEMPLATE.md"
    template_file.write_text("Test issue template")

    # Change to the tmp_path directory so the template can be found
    import os
    original_dir = os.getcwd()
    try:
        os.chdir(tmp_path)
        # Act
        result = find_issue_template_step(ctx)
        if result.metadata:
            ctx.data.update(result.metadata)
    finally:
        os.chdir(original_dir)

    # Assert
    assert isinstance(result, Success)
    assert ctx.get("issue_template") == "Test issue template"

@patch("titan_plugin_github.steps.issue_steps.IssueGeneratorAgent")
def test_ai_suggest_issue_title_and_body(MockIssueGeneratorAgent, mock_secret_manager):
    # Arrange
    mock_issue_generator = MockIssueGeneratorAgent.return_value
    mock_issue_generator.generate_issue.return_value = ("Test Title", "Test Body")
    ctx = WorkflowContext(secrets=mock_secret_manager, data={"issue_body": "Test issue body"})
    ctx.ai = MagicMock()
    ctx.ui = MagicMock()

    # Act
    result = ai_suggest_issue_title_and_body(ctx)
    if result.metadata:
        ctx.data.update(result.metadata)

    # Assert
    assert isinstance(result, Success)
    assert ctx.get("issue_title") == "Test Title"
    assert ctx.get("issue_body") == "Test Body"

def test_preview_and_confirm_issue_step(mock_secret_manager):
    # Arrange
    ctx = WorkflowContext(secrets=mock_secret_manager, data={"issue_title": "Test Title", "issue_body": "Test Body"})
    ctx.ui = MagicMock()
    ctx.views = MagicMock()
    ctx.console = MagicMock()
    ctx.views.prompts.ask_confirm.return_value = True

    # Act
    result = preview_and_confirm_issue_step(ctx)

    # Assert
    assert isinstance(result, Success)

def test_prompt_for_self_assign_step(mock_secret_manager):
    # Arrange
    ctx = WorkflowContext(secrets=mock_secret_manager, data={})
    ctx.github = MagicMock()
    ctx.views = MagicMock()
    ctx.github.get_current_user.return_value = "testuser"
    ctx.views.prompts.ask_confirm.return_value = True

    # Act
    result = prompt_for_self_assign_step(ctx)
    if result.metadata:
        ctx.data.update(result.metadata)

    # Assert
    assert isinstance(result, Success)
    assert ctx.get("assignees") == ["testuser"]

def test_prompt_for_labels_step(mock_secret_manager):
    # Arrange
    ctx = WorkflowContext(secrets=mock_secret_manager, data={})
    ctx.github = MagicMock()
    ctx.views = MagicMock()
    ctx.github.list_labels.return_value = ["bug", "feature"]
    ctx.views.prompts.ask_choices.return_value = ["bug"]

    # Act
    result = prompt_for_labels_step(ctx)
    if result.metadata:
        ctx.data.update(result.metadata)

    # Assert
    assert isinstance(result, Success)
    assert ctx.get("labels") == ["bug"]

@patch("titan_plugin_github.clients.github_client.GitHubClient")
def test_create_issue_step(MockGitHubClient, mock_secret_manager):
    # Arrange
    mock_github_client = MockGitHubClient()
    mock_issue = Issue(
        number=1,
        title="Test Issue",
        body="This is a test issue",
        state="OPEN",
        author=User(login="testuser"),
        labels=[],
    )
    mock_github_client.create_issue.return_value = mock_issue
    ctx = WorkflowContext(secrets=mock_secret_manager, data={"issue_title": "Test Title", "issue_body": "Test Body", "assignees": ["testuser"], "labels": ["bug"]})
    ctx.github = mock_github_client

    # Act
    result = create_issue(ctx)
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
