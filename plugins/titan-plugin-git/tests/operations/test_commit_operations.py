"""
Tests for Commit Operations

Tests for pure business logic related to commit message handling.
"""

from titan_plugin_git.operations.commit_operations import (
    build_ai_commit_prompt,
    normalize_commit_message,
    capitalize_commit_subject,
    validate_message_length,
    process_ai_commit_message,
)


class TestBuildAICommitPrompt:
    """Tests for build_ai_commit_prompt function."""

    def test_build_basic_prompt(self):
        """Should build prompt with diff and files."""
        diff = "diff --git a/file.py\n+new line"
        files = ["file.py"]
        prompt = build_ai_commit_prompt(diff, files)
        assert "Changed Files" in prompt
        assert "file.py" in prompt
        assert "diff --git a/file.py" in prompt
        assert "CRITICAL Instructions" in prompt

    def test_truncate_long_diff(self):
        """Should truncate diff if too long."""
        diff = "a" * 10000
        files = ["file.py"]
        prompt = build_ai_commit_prompt(diff, files, max_diff_chars=100)
        assert len(prompt) < 1100  # Much shorter than original diff
        assert "truncated" in prompt.lower()

    def test_no_truncation_for_short_diff(self):
        """Should not truncate short diff."""
        diff = "short diff"
        files = ["file.py"]
        prompt = build_ai_commit_prompt(diff, files, max_diff_chars=100)
        assert "truncated" not in prompt.lower()
        assert "short diff" in prompt

    def test_multiple_files(self):
        """Should list all files."""
        diff = "diff content"
        files = ["file1.py", "file2.py", "file3.py"]
        prompt = build_ai_commit_prompt(diff, files)
        assert "file1.py" in prompt
        assert "file2.py" in prompt
        assert "file3.py" in prompt
        assert "3 total" in prompt

    def test_empty_files_list(self):
        """Should handle empty files list."""
        diff = "diff content"
        files = []
        prompt = build_ai_commit_prompt(diff, files)
        assert "(checking diff)" in prompt


class TestNormalizeCommitMessage:
    """Tests for normalize_commit_message function."""

    def test_remove_double_quotes(self):
        """Should remove surrounding double quotes."""
        result = normalize_commit_message('"feat: Add feature"')
        assert result == "feat: Add feature"

    def test_remove_single_quotes(self):
        """Should remove surrounding single quotes."""
        result = normalize_commit_message("'fix: Fix bug'")
        assert result == "fix: Fix bug"

    def test_strip_whitespace(self):
        """Should strip leading/trailing whitespace."""
        result = normalize_commit_message("  feat: Add feature  ")
        assert result == "feat: Add feature"

    def test_take_first_line(self):
        """Should take only first line."""
        result = normalize_commit_message("feat: Add feature\n\nBody text\nMore body")
        assert result == "feat: Add feature"

    def test_combined_normalization(self):
        """Should apply all normalizations."""
        result = normalize_commit_message('  "feat: Add feature"  \n\nBody')
        assert result == "feat: Add feature"

    def test_already_normalized(self):
        """Should not change already normalized message."""
        result = normalize_commit_message("feat: Add feature")
        assert result == "feat: Add feature"

    def test_empty_string(self):
        """Should handle empty string."""
        result = normalize_commit_message("")
        assert result == ""


class TestCapitalizeCommitSubject:
    """Tests for capitalize_commit_subject function."""

    def test_capitalize_lowercase_subject(self):
        """Should capitalize lowercase subject."""
        result = capitalize_commit_subject("feat: add new feature")
        assert result == "feat: Add new feature"

    def test_preserve_capitalized_subject(self):
        """Should preserve already capitalized subject."""
        result = capitalize_commit_subject("feat: Add new feature")
        assert result == "feat: Add new feature"

    def test_no_colon(self):
        """Should return unchanged if no colon."""
        result = capitalize_commit_subject("no colon here")
        assert result == "no colon here"

    def test_multiple_colons(self):
        """Should handle multiple colons (split on first)."""
        result = capitalize_commit_subject("feat: add feature: with colon")
        assert result == "feat: Add feature: with colon"

    def test_empty_subject(self):
        """Should handle empty subject after colon."""
        result = capitalize_commit_subject("feat:")
        assert result == "feat: "  # Strip adds space for empty subject

    def test_whitespace_after_colon(self):
        """Should handle whitespace after colon."""
        result = capitalize_commit_subject("feat:   add feature")
        assert result == "feat: Add feature"

    def test_different_commit_types(self):
        """Should work with all commit types."""
        assert capitalize_commit_subject("fix: resolve bug") == "fix: Resolve bug"
        assert capitalize_commit_subject("refactor: improve code") == "refactor: Improve code"
        assert capitalize_commit_subject("docs: update readme") == "docs: Update readme"


class TestValidateMessageLength:
    """Tests for validate_message_length function."""

    def test_valid_length(self):
        """Should pass for short messages."""
        is_valid, length = validate_message_length("Short message")
        assert is_valid is True
        assert length == 13

    def test_exactly_max_length(self):
        """Should pass for message exactly at max length."""
        message = "a" * 72
        is_valid, length = validate_message_length(message, max_length=72)
        assert is_valid is True
        assert length == 72

    def test_too_long(self):
        """Should fail for too long messages."""
        message = "a" * 100
        is_valid, length = validate_message_length(message, max_length=72)
        assert is_valid is False
        assert length == 100

    def test_custom_max_length(self):
        """Should use custom max length."""
        message = "a" * 50
        is_valid, _ = validate_message_length(message, max_length=40)
        assert is_valid is False

        is_valid, _ = validate_message_length(message, max_length=60)
        assert is_valid is True

    def test_empty_string(self):
        """Should handle empty string."""
        is_valid, length = validate_message_length("")
        assert is_valid is True
        assert length == 0


class TestProcessAICommitMessage:
    """Tests for process_ai_commit_message function."""

    def test_complete_pipeline(self):
        """Should normalize and capitalize."""
        result = process_ai_commit_message('"feat: add new feature"')
        assert result == "feat: Add new feature"

    def test_quoted_lowercase(self):
        """Should handle quoted lowercase message."""
        result = process_ai_commit_message("'fix: resolve bug'")
        assert result == "fix: Resolve bug"

    def test_multiline_with_quotes(self):
        """Should handle multiline quoted message."""
        result = process_ai_commit_message('"feat: add feature"\n\nBody text')
        assert result == "feat: Add feature"

    def test_whitespace_and_quotes(self):
        """Should handle whitespace and quotes."""
        result = process_ai_commit_message('  "refactor: improve code"  ')
        assert result == "refactor: Improve code"

    def test_already_perfect(self):
        """Should not change already perfect message."""
        result = process_ai_commit_message("feat: Add new feature")
        assert result == "feat: Add new feature"

    def test_no_conventional_format(self):
        """Should handle non-conventional format."""
        result = process_ai_commit_message('"Add new feature"')
        assert result == "Add new feature"
