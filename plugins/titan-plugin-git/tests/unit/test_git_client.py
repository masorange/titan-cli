"""
Unit tests for Git Client Facade
"""

import pytest
from unittest.mock import patch
from titan_cli.core.result import ClientSuccess, ClientError
from titan_plugin_git.clients.git_client import GitClient


@pytest.fixture
def mock_services():
    """Mock all services"""
    with patch('titan_plugin_git.clients.git_client.GitNetwork') as mock_network, \
         patch('titan_plugin_git.clients.git_client.BranchService') as mock_branch, \
         patch('titan_plugin_git.clients.git_client.CommitService') as mock_commit, \
         patch('titan_plugin_git.clients.git_client.StatusService') as mock_status, \
         patch('titan_plugin_git.clients.git_client.DiffService') as mock_diff, \
         patch('titan_plugin_git.clients.git_client.RemoteService') as mock_remote, \
         patch('titan_plugin_git.clients.git_client.StashService') as mock_stash, \
         patch('titan_plugin_git.clients.git_client.TagService') as mock_tag, \
         patch('titan_plugin_git.clients.git_client.WorktreeService') as mock_worktree:

        yield {
            'network': mock_network.return_value,
            'branch': mock_branch.return_value,
            'commit': mock_commit.return_value,
            'status': mock_status.return_value,
            'diff': mock_diff.return_value,
            'remote': mock_remote.return_value,
            'stash': mock_stash.return_value,
            'tag': mock_tag.return_value,
            'worktree': mock_worktree.return_value,
        }


@pytest.mark.unit
class TestGitClientBranchDelegation:
    """Test that GitClient delegates to BranchService"""

    def test_get_current_branch_delegates(self, mock_services):
        """Test get_current_branch delegates to BranchService"""
        mock_services['branch'].get_current_branch.return_value = ClientSuccess(
            data="main",
            message="Current branch: main"
        )

        client = GitClient()
        result = client.get_current_branch()

        assert isinstance(result, ClientSuccess)
        assert result.data == "main"
        mock_services['branch'].get_current_branch.assert_called_once()

    def test_get_branches_delegates(self, mock_services):
        """Test get_branches delegates to BranchService"""
        from titan_plugin_git.models.view import UIGitBranch

        mock_branches = [
            UIGitBranch(name="main", display_name="* main", is_current=True, is_remote=False),
            UIGitBranch(name="feature", display_name="  feature", is_current=False, is_remote=False),
        ]
        mock_services['branch'].get_branches.return_value = ClientSuccess(
            data=mock_branches,
            message="Found 2 branches"
        )

        client = GitClient()
        result = client.get_branches(remote=False)

        assert isinstance(result, ClientSuccess)
        assert len(result.data) == 2
        mock_services['branch'].get_branches.assert_called_once_with(remote=False)

    def test_create_branch_delegates(self, mock_services):
        """Test create_branch delegates to BranchService"""
        mock_services['branch'].create_branch.return_value = ClientSuccess(
            data=None,
            message="Branch created"
        )

        client = GitClient()
        result = client.create_branch("new-feature", "HEAD")

        assert isinstance(result, ClientSuccess)
        mock_services['branch'].create_branch.assert_called_once_with("new-feature", "HEAD")

    def test_checkout_delegates(self, mock_services):
        """Test checkout delegates to BranchService"""
        mock_services['branch'].checkout.return_value = ClientSuccess(
            data=None,
            message="Checked out"
        )

        client = GitClient()
        result = client.checkout("feature")

        assert isinstance(result, ClientSuccess)
        mock_services['branch'].checkout.assert_called_once_with("feature")


@pytest.mark.unit
class TestGitClientCommitDelegation:
    """Test that GitClient delegates to CommitService"""

    def test_commit_delegates(self, mock_services):
        """Test commit delegates to CommitService"""
        mock_services['commit'].commit.return_value = ClientSuccess(
            data="abc1234567890",
            message="Commit created"
        )

        client = GitClient()
        result = client.commit("feat: Add feature", all=True, no_verify=True)

        assert isinstance(result, ClientSuccess)
        assert result.data == "abc1234567890"
        mock_services['commit'].commit.assert_called_once_with(
            "feat: Add feature",
            True,
            True
        )

    def test_get_current_commit_delegates(self, mock_services):
        """Test get_current_commit delegates to CommitService"""
        mock_services['commit'].get_current_commit.return_value = ClientSuccess(
            data="abc1234567890",
            message="Current commit"
        )

        client = GitClient()
        result = client.get_current_commit()

        assert isinstance(result, ClientSuccess)
        mock_services['commit'].get_current_commit.assert_called_once()


@pytest.mark.unit
class TestGitClientStatusDelegation:
    """Test that GitClient delegates to StatusService"""

    def test_get_status_delegates(self, mock_services):
        """Test get_status delegates to StatusService"""
        from titan_plugin_git.models.view import UIGitStatus

        mock_status = UIGitStatus(
            branch="main",
            is_clean=True,
            modified_files=[],
            untracked_files=[],
            staged_files=[],
            clean_icon="✓",
            status_summary="Clean"
        )
        mock_services['status'].get_status.return_value = ClientSuccess(
            data=mock_status,
            message="Status retrieved"
        )

        client = GitClient()
        result = client.get_status()

        assert isinstance(result, ClientSuccess)
        assert result.data.branch == "main"
        mock_services['status'].get_status.assert_called_once()

    def test_has_uncommitted_changes_delegates(self, mock_services):
        """Test has_uncommitted_changes delegates to StatusService"""
        mock_services['status'].has_uncommitted_changes.return_value = ClientSuccess(
            data=False,
            message="No uncommitted changes"
        )

        client = GitClient()
        result = client.has_uncommitted_changes()

        assert isinstance(result, ClientSuccess)
        assert result.data is False
        mock_services['status'].has_uncommitted_changes.assert_called_once()


@pytest.mark.unit
class TestGitClientRemoteDelegation:
    """Test that GitClient delegates to RemoteService"""

    def test_push_delegates(self, mock_services):
        """Test push delegates to RemoteService"""
        mock_services['remote'].push.return_value = ClientSuccess(
            data=None,
            message="Pushed"
        )

        client = GitClient()
        result = client.push("origin", "main", set_upstream=True, tags=False)

        assert isinstance(result, ClientSuccess)
        mock_services['remote'].push.assert_called_once_with(
            "origin",
            "main",
            True,
            False
        )

    def test_fetch_delegates(self, mock_services):
        """Test fetch delegates to RemoteService"""
        mock_services['remote'].fetch.return_value = ClientSuccess(
            data=None,
            message="Fetched"
        )

        client = GitClient()
        result = client.fetch("origin", "main", all=False)

        assert isinstance(result, ClientSuccess)
        mock_services['remote'].fetch.assert_called_once_with("origin", "main", False)


@pytest.mark.unit
class TestGitClientProtectedBranch:
    """Test GitClient.is_protected_branch()"""

    def test_is_protected_branch_main(self, mock_services):
        """Test that main is protected"""
        client = GitClient()
        assert client.is_protected_branch("main") is True

    def test_is_protected_branch_master(self, mock_services):
        """Test that master is protected"""
        client = GitClient()
        assert client.is_protected_branch("master") is True

    def test_is_protected_branch_feature(self, mock_services):
        """Test that feature branches are not protected"""
        client = GitClient()
        assert client.is_protected_branch("feature-123") is False


@pytest.mark.unit
class TestGitClientSafeDeleteBranch:
    """Test GitClient.safe_delete_branch()"""

    def test_safe_delete_branch_protected(self, mock_services):
        """Test safe_delete_branch refuses to delete protected branch"""
        client = GitClient()
        result = client.safe_delete_branch("main", force=False)

        assert isinstance(result, ClientError)
        assert result.error_code == "BRANCH_PROTECTED"

    def test_safe_delete_branch_allowed(self, mock_services):
        """Test safe_delete_branch allows deleting non-protected branch"""
        mock_services['branch'].delete_branch.return_value = ClientSuccess(
            data=None,
            message="Branch deleted"
        )

        client = GitClient()
        result = client.safe_delete_branch("feature", force=False)

        assert isinstance(result, ClientSuccess)
        mock_services['branch'].delete_branch.assert_called_once_with("feature", False)


@pytest.mark.unit
class TestGitClientWorktreeDelegation:
    """Test that GitClient delegates new worktree methods to WorktreeService"""

    def test_checkout_branch_in_worktree_delegates(self, mock_services):
        """Test checkout_branch_in_worktree delegates to WorktreeService"""
        mock_services['worktree'].checkout_branch_in_worktree.return_value = ClientSuccess(
            data=None,
            message="Checked out branch 'notes/release'"
        )

        client = GitClient()
        result = client.checkout_branch_in_worktree("/tmp/worktree", "notes/release", force=True)

        assert isinstance(result, ClientSuccess)
        mock_services['worktree'].checkout_branch_in_worktree.assert_called_once_with(
            "/tmp/worktree", "notes/release", True
        )

    def test_checkout_branch_in_worktree_error_propagates(self, mock_services):
        """Test checkout_branch_in_worktree propagates ClientError from service"""
        mock_services['worktree'].checkout_branch_in_worktree.return_value = ClientError(
            error_message="branch already exists",
            error_code="WORKTREE_CHECKOUT_ERROR"
        )

        client = GitClient()
        result = client.checkout_branch_in_worktree("/tmp/worktree", "feature")

        assert isinstance(result, ClientError)
        assert result.error_code == "WORKTREE_CHECKOUT_ERROR"

    def test_commit_in_worktree_delegates(self, mock_services):
        """Test commit_in_worktree delegates to WorktreeService"""
        mock_services['worktree'].commit_in_worktree.return_value = ClientSuccess(
            data="abc123def456",
            message="Commit created"
        )

        client = GitClient()
        result = client.commit_in_worktree("/tmp/worktree", "Fix bug", add_all=True, no_verify=False)

        assert isinstance(result, ClientSuccess)
        assert result.data == "abc123def456"
        mock_services['worktree'].commit_in_worktree.assert_called_once_with(
            "/tmp/worktree", "Fix bug", True, False
        )

    def test_commit_in_worktree_error_propagates(self, mock_services):
        """Test commit_in_worktree propagates ClientError from service"""
        mock_services['worktree'].commit_in_worktree.return_value = ClientError(
            error_message="nothing to commit",
            error_code="WORKTREE_COMMIT_ERROR"
        )

        client = GitClient()
        result = client.commit_in_worktree("/tmp/worktree", "Msg")

        assert isinstance(result, ClientError)
        assert result.error_code == "WORKTREE_COMMIT_ERROR"
