# plugins/titan-plugin-git/tests/test_git_plugin.py
import pytest
from unittest.mock import MagicMock
from titan_cli.engine import WorkflowContext, is_success, is_error
from titan_plugin_git.steps.status_step import get_git_status_step
from titan_plugin_git.clients.git_client import GitClient
from titan_plugin_git.models import GitStatus

def test_get_git_status_step_success():
    """
    Test that get_git_status_step successfully retrieves git status.
    """
    # 1. Arrange
    mock_git_client = MagicMock(spec=GitClient)
    mock_status = GitStatus(
        branch="main",
        is_clean=True,
        modified_files=[],
        untracked_files=[],
        staged_files=[],
        ahead=0,
        behind=0
    )
    mock_git_client.get_status.return_value = mock_status
    
    mock_context = MagicMock(spec=WorkflowContext)
    mock_context.git = mock_git_client
    
    # 2. Act
    result = get_git_status_step(mock_context)
    
    # 3. Assert
    assert is_success(result)
    assert result.metadata['git_status'] == mock_status
    mock_git_client.get_status.assert_called_once()


def test_get_git_status_step_no_client():
    """
    Test that get_git_status_step returns an Error if no git client is available.
    """
    # 1. Arrange
    mock_context = MagicMock(spec=WorkflowContext)
    mock_context.git = None
    
    # 2. Act
    result = get_git_status_step(mock_context)
    
    # 3. Assert
    assert is_error(result)
    assert "Git client is not available" in result.message


def test_get_git_status_step_client_error():
    """
    Test that get_git_status_step returns an Error if the client raises an exception.
    """
    # 1. Arrange
    mock_git_client = MagicMock(spec=GitClient)
    mock_git_client.get_status.side_effect = Exception("A git error occurred")
    
    mock_context = MagicMock(spec=WorkflowContext)
    mock_context.git = mock_git_client
    
    # 2. Act
    result = get_git_status_step(mock_context)
    
    # 3. Assert
    assert is_error(result)
    assert "Failed to get git status" in result.message
    assert "A git error occurred" in result.message
