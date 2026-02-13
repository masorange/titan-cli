"""
Unit tests for comment mappers
"""

from titan_plugin_github.models.network.graphql import GraphQLPullRequestReviewComment, GraphQLUser
from titan_plugin_github.models.mappers.comment_mapper import from_graphql_review_comment


class TestFromGraphQLReviewComment:
    """Test GraphQL review comment to UI comment mapping"""

    def test_maps_all_fields_correctly(self):
        """Test that all fields are mapped correctly"""
        # Arrange
        author = GraphQLUser(login="reviewer", name="Reviewer Name")
        graphql_comment = GraphQLPullRequestReviewComment(
            databaseId=12345,
            body="This needs to be fixed",
            author=author,
            createdAt="2025-01-15T10:30:45Z",
            updatedAt="2025-01-15T11:00:00Z",
            path="src/main.py",
            line=42,
            diffHunk="@@ -40,7 +40,7 @@\n def main():\n-    old_code()\n+    new_code()\n"
        )

        # Act
        ui_comment = from_graphql_review_comment(graphql_comment)

        # Assert
        assert ui_comment.id == 12345
        assert ui_comment.body == "This needs to be fixed"
        assert ui_comment.author_login == "reviewer"
        assert ui_comment.author_name == "Reviewer Name"
        assert ui_comment.formatted_date == "15/01/2025 10:30:45"
        assert ui_comment.path == "src/main.py"
        assert ui_comment.line == 42
        assert ui_comment.diff_hunk is not None

    def test_uses_login_as_name_when_name_missing(self):
        """Test fallback to login when author name is not available"""
        # Arrange
        author = GraphQLUser(login="reviewer", name=None)
        graphql_comment = GraphQLPullRequestReviewComment(
            databaseId=1,
            body="Comment",
            author=author,
            createdAt="2025-01-15T10:00:00Z",
            updatedAt="2025-01-15T10:00:00Z",
        )

        # Act
        ui_comment = from_graphql_review_comment(graphql_comment)

        # Assert
        assert ui_comment.author_login == "reviewer"
        assert ui_comment.author_name == "reviewer"  # Falls back to login

    def test_handles_outdated_comment_with_original_line(self):
        """Test that outdated comments use originalLine"""
        # Arrange
        author = GraphQLUser(login="reviewer")
        graphql_comment = GraphQLPullRequestReviewComment(
            databaseId=1,
            body="Outdated comment",
            author=author,
            createdAt="2025-01-15T10:00:00Z",
            updatedAt="2025-01-15T10:00:00Z",
            path="src/old.py",
            line=None,  # Current line is None for outdated
            originalLine=50,  # Original line where it was
        )

        # Act
        ui_comment = from_graphql_review_comment(graphql_comment, is_outdated=True)

        # Assert
        assert ui_comment.line == 50  # Uses originalLine

    def test_handles_missing_diff_hunk(self):
        """Test handling of None diff_hunk"""
        # Arrange
        author = GraphQLUser(login="reviewer")
        graphql_comment = GraphQLPullRequestReviewComment(
            databaseId=1,
            body="Comment",
            author=author,
            createdAt="2025-01-15T10:00:00Z",
            updatedAt="2025-01-15T10:00:00Z",
            diffHunk=None
        )

        # Act
        ui_comment = from_graphql_review_comment(graphql_comment)

        # Assert
        assert ui_comment.diff_hunk is None

    def test_handles_unknown_author(self):
        """Test handling of missing author"""
        # Arrange
        graphql_comment = GraphQLPullRequestReviewComment(
            databaseId=1,
            body="Comment",
            author=None,
            createdAt="2025-01-15T10:00:00Z",
            updatedAt="2025-01-15T10:00:00Z",
        )

        # Act
        ui_comment = from_graphql_review_comment(graphql_comment)

        # Assert
        assert ui_comment.author_login == "Unknown"
        assert ui_comment.author_name == "Unknown"

    def test_preserves_multiline_body(self):
        """Test that multiline comment bodies are preserved"""
        # Arrange
        author = GraphQLUser(login="reviewer")
        multiline_body = """This is a comment
with multiple lines
that should be preserved"""

        graphql_comment = GraphQLPullRequestReviewComment(
            databaseId=1,
            body=multiline_body,
            author=author,
            createdAt="2025-01-15T10:00:00Z",
            updatedAt="2025-01-15T10:00:00Z",
        )

        # Act
        ui_comment = from_graphql_review_comment(graphql_comment)

        # Assert
        assert ui_comment.body == multiline_body
        assert "\n" in ui_comment.body
