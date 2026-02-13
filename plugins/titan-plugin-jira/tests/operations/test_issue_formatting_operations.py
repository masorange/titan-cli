"""
Tests for Issue Formatting Operations

Tests for pure business logic related to formatting Jira issues.
"""

from titan_plugin_jira.operations.issue_formatting_operations import (
    truncate_summary,
    format_issue_field,
    build_issue_table_row,
    get_issue_table_headers,
    build_issue_table_data,
)


class TestTruncateSummary:
    """Tests for truncate_summary function."""

    def test_short_summary(self):
        """Should not truncate short summary."""
        result = truncate_summary("Short summary")
        assert result == "Short summary"

    def test_long_summary(self):
        """Should truncate long summary."""
        long_summary = "A" * 100
        result = truncate_summary(long_summary, max_length=60)
        assert len(result) == 60
        assert result == "A" * 60

    def test_none_summary(self):
        """Should return default for None."""
        result = truncate_summary(None)
        assert result == "No summary"

    def test_empty_summary(self):
        """Should return default for empty string."""
        result = truncate_summary("")
        assert result == "No summary"

    def test_whitespace_only(self):
        """Should return default for whitespace-only."""
        result = truncate_summary("   ")
        assert result == "No summary"

    def test_custom_max_length(self):
        """Should respect custom max length."""
        result = truncate_summary("123456789", max_length=5)
        assert result == "12345"

    def test_exactly_max_length(self):
        """Should not truncate when exactly at max."""
        result = truncate_summary("12345", max_length=5)
        assert result == "12345"


class TestFormatIssueField:
    """Tests for format_issue_field function."""

    def test_valid_value(self):
        """Should return value when valid."""
        result = format_issue_field("John Doe")
        assert result == "John Doe"

    def test_none_value(self):
        """Should return default for None."""
        result = format_issue_field(None)
        assert result == "Unknown"

    def test_empty_string(self):
        """Should return default for empty string."""
        result = format_issue_field("")
        assert result == "Unknown"

    def test_whitespace_only(self):
        """Should return default for whitespace-only."""
        result = format_issue_field("   ")
        assert result == "Unknown"

    def test_custom_default(self):
        """Should use custom default value."""
        result = format_issue_field(None, default="N/A")
        assert result == "N/A"

    def test_unassigned_default(self):
        """Should use 'Unassigned' as default."""
        result = format_issue_field(None, default="Unassigned")
        assert result == "Unassigned"


class TestBuildIssueTableRow:
    """Tests for build_issue_table_row function."""

    def test_full_data(self):
        """Should build row with all fields."""
        row = build_issue_table_row(
            index=1,
            issue_key="PROJ-123",
            status="Open",
            summary="Fix bug",
            assignee="Alice",
            issue_type="Bug",
            priority="High"
        )
        assert row == ["1", "PROJ-123", "Open", "Fix bug", "Alice", "Bug", "High"]

    def test_with_none_values(self):
        """Should use defaults for None values."""
        row = build_issue_table_row(
            index=1,
            issue_key="PROJ-1",
            status=None,
            summary=None,
            assignee=None,
            issue_type=None,
            priority=None
        )
        assert row[2] == "Unknown"  # status
        assert row[3] == "No summary"  # summary
        assert row[4] == "Unassigned"  # assignee
        assert row[5] == "Unknown"  # issue_type
        assert row[6] == "Unknown"  # priority

    def test_truncates_long_summary(self):
        """Should truncate long summary."""
        long_summary = "A" * 100
        row = build_issue_table_row(
            index=1,
            issue_key="PROJ-1",
            status="Open",
            summary=long_summary,
            assignee="Alice",
            issue_type="Bug",
            priority="High",
            summary_max_length=20
        )
        assert len(row[3]) == 20

    def test_index_as_string(self):
        """Should convert index to string."""
        row = build_issue_table_row(
            index=42,
            issue_key="PROJ-1",
            status="Open",
            summary="Test",
            assignee="Alice",
            issue_type="Bug",
            priority="High"
        )
        assert row[0] == "42"
        assert isinstance(row[0], str)


class TestGetIssueTableHeaders:
    """Tests for get_issue_table_headers function."""

    def test_returns_standard_headers(self):
        """Should return standard headers."""
        headers = get_issue_table_headers()
        assert headers == ["#", "Key", "Status", "Summary", "Assignee", "Type", "Priority"]

    def test_returns_list(self):
        """Should return a list."""
        headers = get_issue_table_headers()
        assert isinstance(headers, list)

    def test_has_seven_columns(self):
        """Should have 7 columns."""
        headers = get_issue_table_headers()
        assert len(headers) == 7


class TestBuildIssueTableData:
    """Tests for build_issue_table_data function."""

    def test_empty_issues(self):
        """Should handle empty issue list."""
        headers, rows = build_issue_table_data([])
        assert headers == get_issue_table_headers()
        assert rows == []

    def test_single_issue(self):
        """Should build table for single issue."""
        class MockIssue:
            key = "PROJ-1"
            status = "Open"
            summary = "Fix bug"
            assignee = "Alice"
            issue_type = "Bug"
            priority = "High"

        headers, rows = build_issue_table_data([MockIssue()])
        assert len(headers) == 7
        assert len(rows) == 1
        assert rows[0][1] == "PROJ-1"
        assert rows[0][2] == "Open"

    def test_multiple_issues(self):
        """Should build table for multiple issues."""
        class MockIssue:
            def __init__(self, key):
                self.key = key
                self.status = "Open"
                self.summary = "Summary"
                self.assignee = "Alice"
                self.issue_type = "Bug"
                self.priority = "High"

        issues = [MockIssue("PROJ-1"), MockIssue("PROJ-2"), MockIssue("PROJ-3")]
        headers, rows = build_issue_table_data(issues)
        assert len(rows) == 3
        assert rows[0][0] == "1"
        assert rows[1][0] == "2"
        assert rows[2][0] == "3"

    def test_missing_attributes(self):
        """Should handle issues with missing attributes."""
        class PartialIssue:
            key = "PROJ-1"
            # Missing other attributes

        headers, rows = build_issue_table_data([PartialIssue()])
        assert len(rows) == 1
        assert rows[0][2] == "Unknown"  # status
        assert rows[0][4] == "Unassigned"  # assignee

    def test_custom_summary_length(self):
        """Should respect custom summary max length."""
        class MockIssue:
            key = "PROJ-1"
            status = "Open"
            summary = "A" * 100
            assignee = "Alice"
            issue_type = "Bug"
            priority = "High"

        headers, rows = build_issue_table_data([MockIssue()], summary_max_length=20)
        assert len(rows[0][3]) == 20
