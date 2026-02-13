"""
Unit tests for formatting utilities
"""

from titan_plugin_github.models.formatting import (
    format_date,
    get_pr_status_icon,
    format_pr_stats,
    format_branch_info,
    calculate_review_summary,
)


class TestFormatDate:
    """Test date formatting"""

    def test_formats_iso_date_correctly(self):
        """Test formatting ISO 8601 date"""
        result = format_date("2025-01-15T10:30:45Z")
        assert result == "15/01/2025 10:30:45"

    def test_formats_iso_date_with_timezone(self):
        """Test formatting ISO date with timezone offset"""
        result = format_date("2025-01-15T10:30:45+00:00")
        assert result == "15/01/2025 10:30:45"

    def test_handles_invalid_date(self):
        """Test handling of invalid date string"""
        invalid = "not-a-date"
        result = format_date(invalid)
        # Should return original string if parsing fails
        assert result == invalid

    def test_handles_empty_string(self):
        """Test handling of empty string"""
        result = format_date("")
        assert result == ""


class TestGetPRStatusIcon:
    """Test PR status icon selection"""

    def test_merged_pr_icon(self):
        """Test icon for merged PR"""
        icon = get_pr_status_icon("MERGED", is_draft=False)
        assert icon == "🟣"

    def test_closed_pr_icon(self):
        """Test icon for closed PR"""
        icon = get_pr_status_icon("CLOSED", is_draft=False)
        assert icon == "🔴"

    def test_draft_pr_icon(self):
        """Test icon for draft PR"""
        icon = get_pr_status_icon("OPEN", is_draft=True)
        assert icon == "📝"

    def test_open_pr_icon(self):
        """Test icon for open (non-draft) PR"""
        icon = get_pr_status_icon("OPEN", is_draft=False)
        assert icon == "🟢"

    def test_unknown_state_returns_neutral(self):
        """Test unknown state returns neutral icon"""
        icon = get_pr_status_icon("UNKNOWN", is_draft=False)
        assert icon == "⚪"


class TestFormatPRStats:
    """Test PR statistics formatting"""

    def test_formats_additions_and_deletions(self):
        """Test formatting additions and deletions"""
        result = format_pr_stats(additions=123, deletions=45)
        assert result == "+123 -45"

    def test_formats_zero_values(self):
        """Test formatting with zero values"""
        result = format_pr_stats(additions=0, deletions=0)
        assert result == "+0 -0"

    def test_formats_large_numbers(self):
        """Test formatting large numbers"""
        result = format_pr_stats(additions=9999, deletions=8888)
        assert result == "+9999 -8888"


class TestFormatBranchInfo:
    """Test branch information formatting"""

    def test_formats_branch_names(self):
        """Test formatting branch names"""
        result = format_branch_info(head_ref="feat/new-feature", base_ref="develop")
        assert result == "feat/new-feature → develop"

    def test_formats_main_branch(self):
        """Test formatting with main branch"""
        result = format_branch_info(head_ref="bugfix/issue-123", base_ref="main")
        assert result == "bugfix/issue-123 → main"

    def test_formats_long_branch_names(self):
        """Test formatting long branch names"""
        result = format_branch_info(
            head_ref="feature/very-long-branch-name-with-many-words",
            base_ref="development"
        )
        assert result == "feature/very-long-branch-name-with-many-words → development"


class TestCalculateReviewSummary:
    """Test review summary calculation"""

    def test_no_reviews(self):
        """Test with no reviews"""
        result = calculate_review_summary([])
        assert result == "No reviews"

    def test_all_approved(self):
        """Test with all approved reviews"""
        from unittest.mock import Mock
        reviews = [
            Mock(state="APPROVED"),
            Mock(state="APPROVED"),
        ]
        result = calculate_review_summary(reviews)
        assert result == "✅ 2 approved"

    def test_changes_requested(self):
        """Test with changes requested"""
        from unittest.mock import Mock
        reviews = [
            Mock(state="CHANGES_REQUESTED"),
            Mock(state="APPROVED"),
        ]
        result = calculate_review_summary(reviews)
        assert result == "❌ 1 changes requested"

    def test_mixed_reviews(self):
        """Test with mixed review states"""
        from unittest.mock import Mock
        reviews = [
            Mock(state="APPROVED"),
            Mock(state="CHANGES_REQUESTED"),
            Mock(state="COMMENTED"),
        ]
        result = calculate_review_summary(reviews)
        # Changes requested takes precedence
        assert result == "❌ 1 changes requested"

    def test_only_comments(self):
        """Test with only commented reviews"""
        from unittest.mock import Mock
        reviews = [
            Mock(state="COMMENTED"),
            Mock(state="COMMENTED"),
        ]
        result = calculate_review_summary(reviews)
        assert result == "💬 2 comments"

    def test_multiple_approvals(self):
        """Test with multiple approvals and no changes requested"""
        from unittest.mock import Mock
        reviews = [
            Mock(state="APPROVED"),
            Mock(state="APPROVED"),
            Mock(state="COMMENTED"),
        ]
        result = calculate_review_summary(reviews)
        assert result == "✅ 2 approved"
