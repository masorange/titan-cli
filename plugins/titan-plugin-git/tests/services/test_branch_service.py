"""
Unit tests for Branch Service
"""

import pytest
from unittest.mock import Mock
from titan_cli.core.result import ClientSuccess, ClientError
from titan_plugin_git.clients.services.branch_service import BranchService
from titan_plugin_git.exceptions import GitCommandError


@pytest.fixture
def mock_git_network():
    """Mock GitNetwork instance"""
    return Mock()


@pytest.mark.unit
class TestBranchServiceGetCurrentBranch:
    """Test BranchService.get_current_branch()"""

    def test_get_current_branch_success(self, mock_git_network):
        """Test getting current branch successfully"""
        mock_git_network.run_command.return_value = "main"

        service = BranchService(mock_git_network)
        result = service.get_current_branch()

        assert isinstance(result, ClientSuccess)
        assert result.data == "main"
        mock_git_network.run_command.assert_called_once_with(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"]
        )

    def test_get_current_branch_error(self, mock_git_network):
        """Test error when getting current branch"""
        mock_git_network.run_command.side_effect = GitCommandError("Failed to get branch")

        service = BranchService(mock_git_network)
        result = service.get_current_branch()

        assert isinstance(result, ClientError)
        assert "Failed to get branch" in result.error_message


@pytest.mark.unit
class TestBranchServiceGetBranches:
    """Test BranchService.get_branches()"""

    def test_get_branches_local(self, mock_git_network):
        """Test listing local branches"""
        mock_git_network.run_command.side_effect = [
            "* main\n  feature\n  develop",  # git branch -l
            "",  # upstream check (fails)
        ]

        service = BranchService(mock_git_network)
        result = service.get_branches(remote=False)

        assert isinstance(result, ClientSuccess)
        assert len(result.data) == 3
        assert result.data[0].name == "main"
        assert result.data[0].is_current is True
        assert result.data[1].name == "feature"
        assert result.data[1].is_current is False

    def test_get_branches_remote(self, mock_git_network):
        """Test listing remote branches"""
        mock_git_network.run_command.return_value = "  origin/main\n  origin/feature"

        service = BranchService(mock_git_network)
        result = service.get_branches(remote=True)

        assert isinstance(result, ClientSuccess)
        assert len(result.data) == 2
        assert result.data[0].name == "origin/main"
        assert result.data[0].is_remote is True

    def test_get_branches_skips_origin_head(self, mock_git_network):
        """Test that origin/HEAD is skipped"""
        mock_git_network.run_command.return_value = "  origin/HEAD -> origin/main\n  origin/main"

        service = BranchService(mock_git_network)
        result = service.get_branches(remote=True)

        assert isinstance(result, ClientSuccess)
        assert len(result.data) == 1
        assert result.data[0].name == "origin/main"


@pytest.mark.unit
class TestBranchServiceCreateBranch:
    """Test BranchService.create_branch()"""

    def test_create_branch_success(self, mock_git_network):
        """Test creating branch successfully"""
        service = BranchService(mock_git_network)
        result = service.create_branch("new-feature", "HEAD")

        assert isinstance(result, ClientSuccess)
        mock_git_network.run_command.assert_called_once_with(
            ["git", "branch", "new-feature", "HEAD"]
        )

    def test_create_branch_error(self, mock_git_network):
        """Test error when creating branch"""
        mock_git_network.run_command.side_effect = GitCommandError("Branch already exists")

        service = BranchService(mock_git_network)
        result = service.create_branch("existing", "HEAD")

        assert isinstance(result, ClientError)
        assert "already exists" in result.error_message


@pytest.mark.unit
class TestBranchServiceDeleteBranch:
    """Test BranchService.delete_branch()"""

    def test_delete_branch_success(self, mock_git_network):
        """Test deleting branch successfully"""
        service = BranchService(mock_git_network)
        result = service.delete_branch("old-branch", force=False)

        assert isinstance(result, ClientSuccess)
        mock_git_network.run_command.assert_called_once_with(
            ["git", "branch", "-d", "old-branch"]
        )

    def test_delete_branch_force(self, mock_git_network):
        """Test force deleting branch"""
        service = BranchService(mock_git_network)
        result = service.delete_branch("old-branch", force=True)

        assert isinstance(result, ClientSuccess)
        mock_git_network.run_command.assert_called_once_with(
            ["git", "branch", "-D", "old-branch"]
        )


@pytest.mark.unit
class TestBranchServiceCheckout:
    """Test BranchService.checkout()"""

    def test_checkout_success(self, mock_git_network):
        """Test checkout branch successfully"""
        # Mock show-ref to not raise (branch exists), then checkout succeeds
        def mock_run_command_side_effect(args, check=True):
            if "show-ref" in args:
                return ""  # Branch exists
            if "checkout" in args:
                return ""  # Checkout succeeds
            return ""

        mock_git_network.run_command.side_effect = mock_run_command_side_effect

        service = BranchService(mock_git_network)
        result = service.checkout("feature")

        assert isinstance(result, ClientSuccess)

    def test_checkout_branch_not_found(self, mock_git_network):
        """Test checkout fails when branch doesn't exist"""
        # Mock show-ref to fail (branch doesn't exist)
        mock_git_network.run_command.side_effect = GitCommandError("not found")

        service = BranchService(mock_git_network)
        result = service.checkout("nonexistent")

        assert isinstance(result, ClientError)
        assert result.error_code == "BRANCH_NOT_FOUND"

    def test_checkout_dirty_working_tree(self, mock_git_network):
        """Test checkout fails with uncommitted changes"""
        # Mock show-ref to succeed, checkout to fail with dirty tree
        def mock_run_command_side_effect(args, check=True):
            if "show-ref" in args:
                return ""  # Branch exists
            if "checkout" in args:
                raise GitCommandError("would be overwritten")
            return ""

        mock_git_network.run_command.side_effect = mock_run_command_side_effect

        service = BranchService(mock_git_network)
        result = service.checkout("feature")

        assert isinstance(result, ClientError)
        assert result.error_code == "DIRTY_WORKING_TREE"


@pytest.mark.unit
class TestBranchServiceBranchExistsOnRemote:
    """Test BranchService.branch_exists_on_remote()"""

    def test_branch_exists_on_remote(self, mock_git_network):
        """Test branch exists on remote"""
        mock_git_network.run_command.return_value = "abc123 refs/heads/feature"

        service = BranchService(mock_git_network)
        result = service.branch_exists_on_remote("feature", "origin")

        assert isinstance(result, ClientSuccess)
        assert result.data is True

    def test_branch_does_not_exist_on_remote(self, mock_git_network):
        """Test branch does not exist on remote"""
        mock_git_network.run_command.return_value = ""

        service = BranchService(mock_git_network)
        result = service.branch_exists_on_remote("nonexistent", "origin")

        assert isinstance(result, ClientSuccess)
        assert result.data is False


@pytest.mark.unit
class TestBranchServiceListRecentBranches:
    """Test BranchService.list_recent_branches()"""

    def _outputs(self, for_each_ref: str, reflog: str = ""):
        def run_command(args, **kwargs):
            return reflog if args[1] == "reflog" else for_each_ref
        return run_command

    def test_parses_name_head_upstream_and_date(self, mock_git_network):
        """Test each tab-separated field becomes part of the UI model"""
        mock_git_network.run_command.side_effect = self._outputs(
            "feature\t*\torigin/feature\t2026-10-19T09:00:00+00:00\n"
            "main\t \torigin/main\t2026-10-01T09:00:00+00:00\n"
        )

        service = BranchService(mock_git_network)
        result = service.list_recent_branches()

        assert isinstance(result, ClientSuccess)
        feature, main = result.data
        assert (feature.name, feature.is_current, feature.upstream_info) == ("feature", True, "→ origin/feature")
        assert feature.formatted_date and main.formatted_date
        assert (main.name, main.is_current) == ("main", False)

    def test_orders_by_the_reflog_and_cuts_at_the_limit(self, mock_git_network):
        """Test the branches HEAD was switched to come first, current one leading"""
        mock_git_network.run_command.side_effect = self._outputs(
            "newest\t \t\t2026-10-19T09:00:00+00:00\n"
            "visited\t \t\t2026-01-01T09:00:00+00:00\n"
            "here\t*\t\t2026-05-01T09:00:00+00:00\n",
            reflog="checkout: moving from here to visited\ncommit: feat: x\n",
        )

        service = BranchService(mock_git_network)
        result = service.list_recent_branches(limit=2)

        assert [b.name for b in result.data] == ["here", "visited"]

    def test_a_repo_without_reflog_keeps_the_date_order(self, mock_git_network):
        """Test an empty reflog (a fresh clone) is not an error"""
        mock_git_network.run_command.side_effect = self._outputs(
            "newest\t \t\t2026-10-19T09:00:00+00:00\nolder\t \t\t2026-01-01T09:00:00+00:00\n"
        )

        service = BranchService(mock_git_network)
        result = service.list_recent_branches()

        assert [b.name for b in result.data] == ["newest", "older"]

    def test_git_failure_becomes_a_client_error(self, mock_git_network):
        """Test a failing git command is reported, not raised"""
        mock_git_network.run_command.side_effect = GitCommandError("boom")

        service = BranchService(mock_git_network)
        result = service.list_recent_branches()

        assert isinstance(result, ClientError)
        assert result.error_code == "BRANCH_LIST_ERROR"
