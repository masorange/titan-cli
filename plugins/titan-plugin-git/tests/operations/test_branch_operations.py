"""
Tests for Branch Operations

Tests for pure business logic related to Git branch management.
"""

from titan_plugin_git.operations.branch_operations import (
    check_branch_exists,
    determine_safe_checkout_target,
    should_delete_before_create,
)


class TestCheckBranchExists:
    """Tests for check_branch_exists function."""

    def test_branch_exists(self):
        """Should return True when branch exists."""
        assert check_branch_exists("main", ["main", "develop"]) is True

    def test_branch_does_not_exist(self):
        """Should return False when branch doesn't exist."""
        assert check_branch_exists("feature", ["main", "develop"]) is False

    def test_empty_branch_list(self):
        """Should return False for empty branch list."""
        assert check_branch_exists("main", []) is False

    def test_case_sensitive(self):
        """Should be case-sensitive."""
        assert check_branch_exists("Main", ["main"]) is False
        assert check_branch_exists("main", ["main"]) is True


class TestDetermineSafeCheckoutTarget:
    """Tests for determine_safe_checkout_target function."""

    def test_not_on_target_branch(self):
        """Should return None when not on the branch to delete."""
        result = determine_safe_checkout_target(
            current_branch="feature",
            branch_to_delete="other",
            main_branch="main",
            all_branches=["main", "feature", "other"]
        )
        assert result is None

    def test_on_target_with_available_main(self):
        """Should return main branch when on target and main exists."""
        result = determine_safe_checkout_target(
            current_branch="feature",
            branch_to_delete="feature",
            main_branch="main",
            all_branches=["main", "feature"]
        )
        assert result == "main"

    def test_on_target_main_not_available(self):
        """Should return None when main branch doesn't exist."""
        result = determine_safe_checkout_target(
            current_branch="feature",
            branch_to_delete="feature",
            main_branch="main",
            all_branches=["feature", "develop"]
        )
        assert result is None

    def test_trying_to_delete_main_itself(self):
        """Should return None when trying to delete main branch."""
        result = determine_safe_checkout_target(
            current_branch="main",
            branch_to_delete="main",
            main_branch="main",
            all_branches=["main", "develop"]
        )
        assert result is None

    def test_on_main_deleting_other(self):
        """Should return None when on main and deleting another branch."""
        result = determine_safe_checkout_target(
            current_branch="main",
            branch_to_delete="feature",
            main_branch="main",
            all_branches=["main", "feature"]
        )
        assert result is None

    def test_master_as_main_branch(self):
        """Should work with 'master' as main branch name."""
        result = determine_safe_checkout_target(
            current_branch="feature",
            branch_to_delete="feature",
            main_branch="master",
            all_branches=["master", "feature"]
        )
        assert result == "master"


class TestShouldDeleteBeforeCreate:
    """Tests for should_delete_before_create function."""

    def test_exists_and_should_delete(self):
        """Should return True when branch exists and deletion requested."""
        assert should_delete_before_create(
            branch_exists=True,
            delete_if_exists=True
        ) is True

    def test_exists_but_no_delete_flag(self):
        """Should return False when branch exists but no deletion requested."""
        assert should_delete_before_create(
            branch_exists=True,
            delete_if_exists=False
        ) is False

    def test_does_not_exist_with_delete_flag(self):
        """Should return False when branch doesn't exist (even with delete flag)."""
        assert should_delete_before_create(
            branch_exists=False,
            delete_if_exists=True
        ) is False

    def test_does_not_exist_no_delete_flag(self):
        """Should return False when branch doesn't exist and no deletion requested."""
        assert should_delete_before_create(
            branch_exists=False,
            delete_if_exists=False
        ) is False
