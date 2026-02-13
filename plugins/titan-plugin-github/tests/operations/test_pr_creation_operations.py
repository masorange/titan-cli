"""
Tests for PR Creation Operations

Tests for pure business logic related to PR creation.
"""

from titan_plugin_github.operations.pr_creation_operations import (
    determine_pr_assignees,
    add_assignee_if_missing,
)


class TestDeterminePRAssignees:
    """Tests for determine_pr_assignees function."""

    def test_auto_assign_with_empty_list(self):
        """Should add current user when auto_assign is True and list is empty."""
        result = determine_pr_assignees(
            auto_assign=True,
            current_user="alice",
            existing_assignees=[]
        )
        assert result == ["alice"]

    def test_auto_assign_with_existing_assignees(self):
        """Should add current user to existing assignees when auto_assign is True."""
        result = determine_pr_assignees(
            auto_assign=True,
            current_user="alice",
            existing_assignees=["bob", "charlie"]
        )
        assert result == ["bob", "charlie", "alice"]

    def test_auto_assign_when_already_in_list(self):
        """Should not duplicate current user if already in list."""
        result = determine_pr_assignees(
            auto_assign=True,
            current_user="alice",
            existing_assignees=["alice", "bob"]
        )
        assert result == ["alice", "bob"]

    def test_no_auto_assign_with_empty_list(self):
        """Should return empty list when auto_assign is False."""
        result = determine_pr_assignees(
            auto_assign=False,
            current_user="alice",
            existing_assignees=[]
        )
        assert result == []

    def test_no_auto_assign_preserves_existing(self):
        """Should preserve existing assignees when auto_assign is False."""
        result = determine_pr_assignees(
            auto_assign=False,
            current_user="alice",
            existing_assignees=["bob"]
        )
        assert result == ["bob"]

    def test_none_existing_assignees_treated_as_empty(self):
        """Should treat None existing_assignees as empty list."""
        result = determine_pr_assignees(
            auto_assign=True,
            current_user="alice",
            existing_assignees=None
        )
        assert result == ["alice"]

    def test_does_not_mutate_original_list(self):
        """Should not mutate the original assignees list."""
        original = ["bob"]
        result = determine_pr_assignees(
            auto_assign=True,
            current_user="alice",
            existing_assignees=original
        )
        assert result == ["bob", "alice"]
        assert original == ["bob"]  # Original unchanged


class TestAddAssigneeIfMissing:
    """Tests for add_assignee_if_missing function."""

    def test_add_to_empty_list(self):
        """Should add assignee to empty list."""
        result = add_assignee_if_missing("alice", [])
        assert result == ["alice"]

    def test_add_to_existing_list(self):
        """Should add assignee to existing list."""
        result = add_assignee_if_missing("alice", ["bob"])
        assert result == ["bob", "alice"]

    def test_do_not_add_duplicate(self):
        """Should not add assignee if already in list."""
        result = add_assignee_if_missing("alice", ["alice"])
        assert result == ["alice"]

    def test_do_not_add_duplicate_with_others(self):
        """Should not add assignee if already in list with others."""
        result = add_assignee_if_missing("alice", ["bob", "alice", "charlie"])
        assert result == ["bob", "alice", "charlie"]

    def test_none_existing_assignees_treated_as_empty(self):
        """Should treat None existing_assignees as empty list."""
        result = add_assignee_if_missing("alice", None)
        assert result == ["alice"]

    def test_does_not_mutate_original_list(self):
        """Should not mutate the original assignees list."""
        original = ["bob"]
        result = add_assignee_if_missing("alice", original)
        assert result == ["bob", "alice"]
        assert original == ["bob"]  # Original unchanged

    def test_preserves_order(self):
        """Should preserve existing order and append new assignee."""
        result = add_assignee_if_missing("david", ["alice", "bob", "charlie"])
        assert result == ["alice", "bob", "charlie", "david"]
