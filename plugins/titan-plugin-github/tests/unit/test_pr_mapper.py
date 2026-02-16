"""
Unit tests for PR mappers
"""

from unittest.mock import Mock
from titan_plugin_github.models.network.rest import NetworkPullRequest, NetworkUser
from titan_plugin_github.models.mappers.pr_mapper import from_rest_pr


class TestFromRestPR:
    """Test REST PR to UI PR mapping"""

    def test_maps_all_fields_correctly(self):
        """Test that all fields are mapped correctly"""
        # Arrange
        author = NetworkUser(login="author123", name="Author Name")
        reviews = [
            Mock(state="APPROVED"),
            Mock(state="APPROVED"),
        ]

        rest_pr = NetworkPullRequest(
            number=42,
            title="feat: Add new feature",
            body="This PR adds a new feature",
            state="OPEN",
            isDraft=False,
            author=author,
            headRefName="feat/new-feature",
            baseRefName="develop",
            mergeable="MERGEABLE",
            additions=123,
            deletions=45,
            changedFiles=5,
            reviews=reviews,
            labels=[{"name": "feature"}, {"name": "enhancement"}],
            createdAt="2025-01-15T10:00:00Z",
            updatedAt="2025-01-15T12:00:00Z",
        )

        # Act
        ui_pr = from_rest_pr(rest_pr)

        # Assert
        assert ui_pr.number == 42
        assert ui_pr.title == "feat: Add new feature"
        assert ui_pr.body == "This PR adds a new feature"
        assert ui_pr.state == "OPEN"
        assert ui_pr.status_icon == "🟢"  # Open, not draft
        assert ui_pr.author_name == "author123"
        assert ui_pr.head_ref == "feat/new-feature"
        assert ui_pr.base_ref == "develop"
        assert ui_pr.branch_info == "feat/new-feature → develop"
        assert ui_pr.stats == "+123 -45"
        assert ui_pr.files_changed == 5
        assert ui_pr.is_mergeable is True
        assert ui_pr.is_draft is False
        assert ui_pr.review_summary == "✅ 2 approved"
        assert ui_pr.labels == ["feature", "enhancement"]
        assert ui_pr.formatted_created_at == "15/01/2025 10:00:00"
        assert ui_pr.formatted_updated_at == "15/01/2025 12:00:00"

    def test_draft_pr_icon(self):
        """Test that draft PRs get the correct icon"""
        # Arrange
        author = NetworkUser(login="author")
        rest_pr = NetworkPullRequest(
            number=1,
            title="WIP: Draft PR",
            body="",
            state="OPEN",
            isDraft=True,
            author=author,
            headRefName="wip/feature",
            baseRefName="main",
            mergeable="MERGEABLE",
            additions=0,
            deletions=0,
            changedFiles=0,
            reviews=[],
            labels=[],
            createdAt="2025-01-15T10:00:00Z",
            updatedAt="2025-01-15T10:00:00Z",
        )

        # Act
        ui_pr = from_rest_pr(rest_pr)

        # Assert
        assert ui_pr.status_icon == "📝"
        assert ui_pr.is_draft is True

    def test_merged_pr_icon(self):
        """Test that merged PRs get the correct icon"""
        # Arrange
        author = NetworkUser(login="author")
        rest_pr = NetworkPullRequest(
            number=1,
            title="Merged PR",
            body="",
            state="MERGED",
            isDraft=False,
            author=author,
            headRefName="feature",
            baseRefName="main",
            mergeable="UNKNOWN",
            additions=10,
            deletions=5,
            changedFiles=1,
            reviews=[Mock(state="APPROVED")],
            labels=[],
            createdAt="2025-01-15T10:00:00Z",
            updatedAt="2025-01-15T10:00:00Z",
        )

        # Act
        ui_pr = from_rest_pr(rest_pr)

        # Assert
        assert ui_pr.status_icon == "🟣"
        assert ui_pr.state == "MERGED"

    def test_closed_pr_icon(self):
        """Test that closed PRs get the correct icon"""
        # Arrange
        author = NetworkUser(login="author")
        rest_pr = NetworkPullRequest(
            number=1,
            title="Closed PR",
            body="",
            state="CLOSED",
            isDraft=False,
            author=author,
            headRefName="feature",
            baseRefName="main",
            mergeable="UNKNOWN",
            additions=0,
            deletions=0,
            changedFiles=0,
            reviews=[],
            labels=[],
            createdAt="2025-01-15T10:00:00Z",
            updatedAt="2025-01-15T10:00:00Z",
        )

        # Act
        ui_pr = from_rest_pr(rest_pr)

        # Assert
        assert ui_pr.status_icon == "🔴"
        assert ui_pr.state == "CLOSED"

    def test_not_mergeable_pr(self):
        """Test PR with conflicts (not mergeable)"""
        # Arrange
        author = NetworkUser(login="author")
        rest_pr = NetworkPullRequest(
            number=1,
            title="Conflicting PR",
            body="",
            state="OPEN",
            isDraft=False,
            author=author,
            headRefName="feature",
            baseRefName="main",
            mergeable="CONFLICTING",
            additions=10,
            deletions=5,
            changedFiles=1,
            reviews=[],
            labels=[],
            createdAt="2025-01-15T10:00:00Z",
            updatedAt="2025-01-15T10:00:00Z",
        )

        # Act
        ui_pr = from_rest_pr(rest_pr)

        # Assert
        assert ui_pr.is_mergeable is False

    def test_handles_empty_labels(self):
        """Test handling of empty labels list"""
        # Arrange
        author = NetworkUser(login="author")
        rest_pr = NetworkPullRequest(
            number=1,
            title="PR",
            body="",
            state="OPEN",
            isDraft=False,
            author=author,
            headRefName="feature",
            baseRefName="main",
            mergeable="MERGEABLE",
            additions=0,
            deletions=0,
            changedFiles=0,
            reviews=[],
            labels=[],
            createdAt="2025-01-15T10:00:00Z",
            updatedAt="2025-01-15T10:00:00Z",
        )

        # Act
        ui_pr = from_rest_pr(rest_pr)

        # Assert
        assert ui_pr.labels == []

    def test_handles_no_reviews(self):
        """Test handling of no reviews"""
        # Arrange
        author = NetworkUser(login="author")
        rest_pr = NetworkPullRequest(
            number=1,
            title="PR",
            body="",
            state="OPEN",
            isDraft=False,
            author=author,
            headRefName="feature",
            baseRefName="main",
            mergeable="MERGEABLE",
            additions=0,
            deletions=0,
            changedFiles=0,
            reviews=[],
            labels=[],
            createdAt="2025-01-15T10:00:00Z",
            updatedAt="2025-01-15T10:00:00Z",
        )

        # Act
        ui_pr = from_rest_pr(rest_pr)

        # Assert
        assert ui_pr.review_summary == "No reviews"

    def test_handles_missing_dates(self):
        """Test handling of None dates"""
        # Arrange
        author = NetworkUser(login="author")
        rest_pr = NetworkPullRequest(
            number=1,
            title="PR",
            body="",
            state="OPEN",
            isDraft=False,
            author=author,
            headRefName="feature",
            baseRefName="main",
            mergeable="MERGEABLE",
            additions=0,
            deletions=0,
            changedFiles=0,
            reviews=[],
            labels=[],
            createdAt=None,
            updatedAt=None,
        )

        # Act
        ui_pr = from_rest_pr(rest_pr)

        # Assert
        assert ui_pr.formatted_created_at == ""
        assert ui_pr.formatted_updated_at == ""
