"""
Tests for Issue Operations

Tests for pure business logic related to GitHub issues.
"""

from titan_plugin_github.operations.issue_operations import (
    parse_comma_separated_list,
    filter_valid_labels,
    parse_assignees_and_labels,
)


class TestParseCommaSeparatedList:
    """Tests for parse_comma_separated_list function."""

    def test_parse_simple_list(self):
        """Should parse simple comma-separated list."""
        result = parse_comma_separated_list("bug, feature, help wanted")
        assert result == ["bug", "feature", "help wanted"]

    def test_parse_no_spaces(self):
        """Should parse list without spaces after commas."""
        result = parse_comma_separated_list("bug,feature,help wanted")
        assert result == ["bug", "feature", "help wanted"]

    def test_parse_with_extra_spaces(self):
        """Should trim extra spaces from items."""
        result = parse_comma_separated_list("  bug  ,  feature  ,  help wanted  ")
        assert result == ["bug", "feature", "help wanted"]

    def test_parse_empty_string(self):
        """Should return empty list for empty string."""
        result = parse_comma_separated_list("")
        assert result == []

    def test_parse_whitespace_only(self):
        """Should return empty list for whitespace-only string."""
        result = parse_comma_separated_list("   ")
        assert result == []

    def test_parse_with_empty_items(self):
        """Should skip empty items from consecutive commas."""
        result = parse_comma_separated_list("bug, , feature, , help wanted")
        assert result == ["bug", "feature", "help wanted"]

    def test_parse_single_item(self):
        """Should parse single item correctly."""
        result = parse_comma_separated_list("bug")
        assert result == ["bug"]

    def test_parse_single_item_with_spaces(self):
        """Should parse single item with spaces."""
        result = parse_comma_separated_list("  bug  ")
        assert result == ["bug"]

    def test_parse_trailing_comma(self):
        """Should handle trailing comma."""
        result = parse_comma_separated_list("bug, feature,")
        assert result == ["bug", "feature"]

    def test_parse_leading_comma(self):
        """Should handle leading comma."""
        result = parse_comma_separated_list(", bug, feature")
        assert result == ["bug", "feature"]


class TestFilterValidLabels:
    """Tests for filter_valid_labels function."""

    def test_all_labels_valid(self):
        """Should return all labels as valid when they exist."""
        valid, invalid = filter_valid_labels(
            selected_labels=["bug", "feature"],
            available_labels=["bug", "feature", "help wanted"]
        )
        assert valid == ["bug", "feature"]
        assert invalid == []

    def test_some_labels_invalid(self):
        """Should separate valid and invalid labels."""
        valid, invalid = filter_valid_labels(
            selected_labels=["bug", "invalid", "feature"],
            available_labels=["bug", "feature"]
        )
        assert valid == ["bug", "feature"]
        assert invalid == ["invalid"]

    def test_all_labels_invalid(self):
        """Should return all labels as invalid when none exist."""
        valid, invalid = filter_valid_labels(
            selected_labels=["invalid1", "invalid2"],
            available_labels=["bug", "feature"]
        )
        assert valid == []
        assert invalid == ["invalid1", "invalid2"]

    def test_empty_selected_labels(self):
        """Should return empty lists for empty selection."""
        valid, invalid = filter_valid_labels(
            selected_labels=[],
            available_labels=["bug", "feature"]
        )
        assert valid == []
        assert invalid == []

    def test_empty_available_labels(self):
        """Should mark all as invalid when no labels available."""
        valid, invalid = filter_valid_labels(
            selected_labels=["bug", "feature"],
            available_labels=[]
        )
        assert valid == []
        assert invalid == ["bug", "feature"]

    def test_preserves_order(self):
        """Should preserve order of selected labels in results."""
        valid, invalid = filter_valid_labels(
            selected_labels=["feature", "invalid", "bug"],
            available_labels=["bug", "feature", "help wanted"]
        )
        assert valid == ["feature", "bug"]
        assert invalid == ["invalid"]

    def test_case_sensitive(self):
        """Should treat labels as case-sensitive."""
        valid, invalid = filter_valid_labels(
            selected_labels=["Bug", "feature"],
            available_labels=["bug", "feature"]
        )
        assert valid == ["feature"]
        assert invalid == ["Bug"]


class TestParseAssigneesAndLabels:
    """Tests for parse_assignees_and_labels function."""

    def test_parse_both_assignees_and_labels(self):
        """Should parse both assignees and labels."""
        assignees, labels = parse_assignees_and_labels(
            assignees_str="alice, bob",
            labels_str="bug, feature"
        )
        assert assignees == ["alice", "bob"]
        assert labels == ["bug", "feature"]

    def test_parse_only_assignees(self):
        """Should parse assignees with no labels."""
        assignees, labels = parse_assignees_and_labels(
            assignees_str="alice, bob",
            labels_str=None
        )
        assert assignees == ["alice", "bob"]
        assert labels == []

    def test_parse_only_labels(self):
        """Should parse labels with no assignees."""
        assignees, labels = parse_assignees_and_labels(
            assignees_str=None,
            labels_str="bug, feature"
        )
        assert assignees == []
        assert labels == ["bug", "feature"]

    def test_parse_both_none(self):
        """Should return empty lists when both are None."""
        assignees, labels = parse_assignees_and_labels(
            assignees_str=None,
            labels_str=None
        )
        assert assignees == []
        assert labels == []

    def test_parse_empty_strings(self):
        """Should return empty lists for empty strings."""
        assignees, labels = parse_assignees_and_labels(
            assignees_str="",
            labels_str=""
        )
        assert assignees == []
        assert labels == []

    def test_parse_whitespace_strings(self):
        """Should return empty lists for whitespace-only strings."""
        assignees, labels = parse_assignees_and_labels(
            assignees_str="   ",
            labels_str="   "
        )
        assert assignees == []
        assert labels == []

    def test_parse_with_extra_spaces(self):
        """Should trim spaces from both assignees and labels."""
        assignees, labels = parse_assignees_and_labels(
            assignees_str="  alice  ,  bob  ",
            labels_str="  bug  ,  feature  "
        )
        assert assignees == ["alice", "bob"]
        assert labels == ["bug", "feature"]

    def test_parse_single_values(self):
        """Should parse single assignee and label."""
        assignees, labels = parse_assignees_and_labels(
            assignees_str="alice",
            labels_str="bug"
        )
        assert assignees == ["alice"]
        assert labels == ["bug"]

    def test_parse_with_empty_items(self):
        """Should skip empty items in both lists."""
        assignees, labels = parse_assignees_and_labels(
            assignees_str="alice, , bob",
            labels_str="bug, , feature"
        )
        assert assignees == ["alice", "bob"]
        assert labels == ["bug", "feature"]
