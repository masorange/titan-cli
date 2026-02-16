"""
Shared fixtures for Git plugin tests
"""

import pytest
from unittest.mock import Mock
from titan_cli.core.result import ClientSuccess, ClientError
from titan_plugin_git.models.network import (
    NetworkGitBranch,
    NetworkGitStatus,
    NetworkGitCommit,
    NetworkGitTag,
    NetworkGitWorktree,
)
from titan_plugin_git.models.view import (
    UIGitBranch,
    UIGitStatus,
    UIGitCommit,
    UIGitTag,
    UIGitWorktree,
)


# ===== Network Model Fixtures =====

@pytest.fixture
def sample_network_branch():
    """Sample network branch model"""
    return NetworkGitBranch(
        name="feature",
        is_current=True,
        is_remote=False,
        upstream="origin/feature"
    )


@pytest.fixture
def sample_network_status():
    """Sample network status model"""
    return NetworkGitStatus(
        branch="main",
        is_clean=False,
        modified_files=["file1.py", "file2.py"],
        untracked_files=["new_file.py"],
        staged_files=["staged.py"],
        ahead=2,
        behind=1
    )


@pytest.fixture
def sample_network_commit():
    """Sample network commit model"""
    return NetworkGitCommit(
        hash="abc1234567890abcdef1234567890abcdef12345",
        message="feat: Add new feature",
        author="John Doe <john@example.com>",
        date="2026-01-15 10:30:00 +0000"
    )


@pytest.fixture
def sample_network_tag():
    """Sample network tag model"""
    return NetworkGitTag(
        name="v1.0.0",
        commit_hash="abc1234567890abcdef1234567890abcdef12345",
        message="Release version 1.0.0"
    )


@pytest.fixture
def sample_network_worktree():
    """Sample network worktree model"""
    return NetworkGitWorktree(
        path="/home/user/project",
        branch="main",
        commit="abc1234567890abcdef1234567890abcdef12345",
        is_bare=False,
        is_detached=False
    )


# ===== UI Model Fixtures =====

@pytest.fixture
def sample_ui_branch():
    """Sample UI branch model"""
    return UIGitBranch(
        name="feature",
        display_name="* feature",
        is_current=True,
        is_remote=False,
        upstream="origin/feature",
        upstream_info="→ origin/feature"
    )


@pytest.fixture
def sample_ui_status():
    """Sample UI status model"""
    return UIGitStatus(
        branch="main",
        is_clean=False,
        modified_files=["file1.py", "file2.py"],
        untracked_files=["new_file.py"],
        staged_files=["staged.py"],
        ahead=2,
        behind=1,
        clean_icon="✗",
        status_summary="2 modified, 1 staged, 1 untracked",
        sync_status="↑2 ↓1"
    )


@pytest.fixture
def sample_ui_commit():
    """Sample UI commit model"""
    return UIGitCommit(
        hash="abc1234567890abcdef1234567890abcdef12345",
        short_hash="abc1234",
        message="feat: Add new feature",
        message_subject="feat: Add new feature",
        author="John Doe <john@example.com>",
        author_short="John Doe",
        date="2026-01-15 10:30:00 +0000",
        formatted_date="2026-01-15 10:30:00 +0000"
    )


@pytest.fixture
def sample_ui_tag():
    """Sample UI tag model"""
    return UIGitTag(
        name="v1.0.0",
        display_name="🏷  v1.0.0",
        commit_hash="abc1234567890abcdef1234567890abcdef12345",
        commit_hash_short="abc1234",
        message="Release version 1.0.0",
        message_summary="Release version 1.0.0"
    )


@pytest.fixture
def sample_ui_worktree():
    """Sample UI worktree model"""
    return UIGitWorktree(
        path="/home/user/project",
        path_short="project",
        branch="main",
        branch_display="main",
        commit="abc1234567890abcdef1234567890abcdef12345",
        commit_short="abc1234",
        is_bare=False,
        is_detached=False,
        status_icon="📂"
    )


# ===== ClientResult Factories =====

@pytest.fixture
def client_success():
    """Factory for creating ClientSuccess instances"""
    def _create(data, message="Success"):
        return ClientSuccess(data=data, message=message)
    return _create


@pytest.fixture
def client_error():
    """Factory for creating ClientError instances"""
    def _create(error_message, error_code="ERROR"):
        return ClientError(error_message=error_message, error_code=error_code)
    return _create


# ===== Mock Client Fixtures =====

@pytest.fixture
def mock_git_client():
    """Mock GitClient instance"""
    return Mock()


@pytest.fixture
def mock_git_network():
    """Mock GitNetwork instance"""
    return Mock()
