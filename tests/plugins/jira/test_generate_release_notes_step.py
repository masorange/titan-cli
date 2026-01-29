"""
Tests for generate_release_notes_step
"""

import pytest
from unittest.mock import MagicMock
from titan_cli.engine import WorkflowContext
from titan_plugin_jira.steps.generate_release_notes_step import (
    group_issues_by_brand,
    extract_affected_brands,
    clean_summary,
)


class TestExtractAffectedBrands:
    """Tests for extract_affected_brands function"""

    def test_extract_brands_from_list(self):
        """Test extraction of brands from list of objects"""
        issue = {
            "fields": {
                "customfield_11931": [
                    {"value": "Yoigo"},
                    {"value": "Jazztel"}
                ]
            }
        }

        brands = extract_affected_brands(issue)

        assert "Yoigo" in brands
        assert "Jazztel" in brands
        assert len(brands) == 2

    def test_extract_all_brands(self):
        """Test that 'All' or 'Todas' returns 'All'"""
        issue = {
            "fields": {
                "customfield_11931": [{"value": "All"}]
            }
        }

        brands = extract_affected_brands(issue)

        assert brands == ["All"]

    def test_extract_todas_as_all(self):
        """Test that 'Todas' is normalized to 'All'"""
        issue = {
            "fields": {
                "customfield_11931": [{"value": "Todas"}]
            }
        }

        brands = extract_affected_brands(issue)

        assert brands == ["All"]

    def test_missing_brands_field_returns_unknown(self):
        """Test that missing brands field returns 'Marca Desconocida'"""
        issue = {
            "fields": {}
        }

        brands = extract_affected_brands(issue)

        assert brands == ["Marca Desconocida"]

    def test_empty_brands_field_returns_unknown(self):
        """Test that empty brands field returns 'Marca Desconocida'"""
        issue = {
            "fields": {
                "customfield_11931": []
            }
        }

        brands = extract_affected_brands(issue)

        assert brands == ["Marca Desconocida"]


class TestGroupIssuesByBrand:
    """Tests for group_issues_by_brand function"""

    def test_group_issues_extracts_description_and_components(self):
        """Test that description and components are extracted from issues"""
        issues = [{
            "key": "ECAPP-123",
            "fields": {
                "summary": "Test issue",
                "description": "Full description here with more context",
                "components": [{"name": "Mobile"}, {"name": "iOS"}],
                "customfield_11931": [{"value": "Yoigo"}]
            }
        }]

        result = group_issues_by_brand(issues)

        # Verify Yoigo has the issue
        assert len(result["Yoigo"]) == 1
        issue_data = result["Yoigo"][0]

        # Verify all fields are extracted
        assert issue_data["key"] == "ECAPP-123"
        assert issue_data["summary"] == "Test issue"
        assert issue_data["description"] == "Full description here with more context"
        assert issue_data["components"] == ["Mobile", "iOS"]

    def test_group_issues_handles_missing_description(self):
        """Test that missing description is handled gracefully"""
        issues = [{
            "key": "ECAPP-124",
            "fields": {
                "summary": "Test without description",
                "components": [],
                "customfield_11931": [{"value": "Jazztel"}]
            }
        }]

        result = group_issues_by_brand(issues)

        issue_data = result["Jazztel"][0]
        assert issue_data["description"] == ""
        assert issue_data["components"] == []

    def test_group_issues_all_brand_appears_in_all_sections(self):
        """Test that issues with 'All' brand appear in all 8 brand sections"""
        issues = [{
            "key": "ECAPP-125",
            "fields": {
                "summary": "Issue for all brands",
                "description": "Affects everyone",
                "components": [{"name": "Core"}],
                "customfield_11931": [{"value": "All"}]
            }
        }]

        result = group_issues_by_brand(issues)

        # Should appear in all 8 brands (not "Marca Desconocida")
        expected_brands = ["Yoigo", "MASMOVIL", "Jazztel", "Lycamobile", "Lebara", "Llamaya", "Guuk", "Sweno"]

        for brand in expected_brands:
            assert len(result[brand]) == 1
            assert result[brand][0]["key"] == "ECAPP-125"

        # Should NOT appear in "Marca Desconocida"
        assert len(result["Marca Desconocida"]) == 0

    def test_group_issues_unknown_brand_goes_to_marca_desconocida(self):
        """Test that issues without brand field go to 'Marca Desconocida'"""
        issues = [{
            "key": "ECAPP-126",
            "fields": {
                "summary": "Issue without brand",
                "description": "No brand assigned",
                "components": []
            }
        }]

        result = group_issues_by_brand(issues)

        # Should only appear in "Marca Desconocida"
        assert len(result["Marca Desconocida"]) == 1
        assert result["Marca Desconocida"][0]["key"] == "ECAPP-126"

        # Should NOT appear in other brands
        for brand in ["Yoigo", "MASMOVIL", "Jazztel", "Lycamobile", "Lebara", "Llamaya", "Guuk", "Sweno"]:
            assert len(result[brand]) == 0


class TestCleanSummary:
    """Tests for clean_summary function"""

    def test_clean_summary_removes_platform_brackets(self):
        """Test that platform prefixes like [iOS], [Android] are removed"""
        summary = "[iOS] Fix login issue"

        cleaned = clean_summary(summary)

        assert cleaned == "Fix login issue"

    def test_clean_summary_removes_multiple_brackets(self):
        """Test that multiple bracket prefixes are removed"""
        summary = "[Android] [Llamaya] Fix crash on startup"

        cleaned = clean_summary(summary)

        assert cleaned == "Fix crash on startup"

    def test_clean_summary_removes_brand_prefixes(self):
        """Test that brand prefixes like 'Yoigo:' are removed"""
        summary = "Yoigo: Update home screen"

        cleaned = clean_summary(summary)

        assert cleaned == "Update home screen"

    def test_clean_summary_removes_technical_prefixes(self):
        """Test that technical prefixes like FIX:, HOTFIX: are removed"""
        summary = "HOTFIX: Correct payment flow"

        cleaned = clean_summary(summary)

        assert cleaned == "Correct payment flow"

    def test_clean_summary_replaces_technical_jargon(self):
        """Test that technical terms are replaced with user-friendly words"""
        summary = "Refactor the logger endpoint"

        cleaned = clean_summary(summary)

        # Should replace "refactor" with "improved" and "logger" with "analytics system"
        assert "improved" in cleaned.lower()
        assert "analytics system" in cleaned.lower()
        assert "endpoint" not in cleaned.lower()  # Should be replaced with "service"

    def test_clean_summary_handles_empty_string(self):
        """Test that empty string is handled gracefully"""
        summary = ""

        cleaned = clean_summary(summary)

        assert cleaned == ""

    def test_clean_summary_removes_extra_whitespace(self):
        """Test that extra whitespace is normalized"""
        summary = "Fix   bug    with   multiple   spaces"

        cleaned = clean_summary(summary)

        assert cleaned == "Fix bug with multiple spaces"


class TestGenerateReleaseNotesStep:
    """Integration tests for generate_release_notes step"""

    @pytest.fixture
    def mock_context(self):
        """Create a mock WorkflowContext"""
        ctx = MagicMock(spec=WorkflowContext)
        ctx.ui = MagicMock()
        ctx.views = MagicMock()
        ctx.ai = None  # AI not available by default
        ctx.current_step = 1
        ctx.total_steps = 5
        return ctx

    def test_generate_release_notes_with_no_issues_returns_error(self, mock_context):
        """Test that step returns Error when no issues are provided"""
        from titan_plugin_jira.steps.generate_release_notes_step import generate_release_notes
        from titan_cli.engine import Error

        mock_context.get.return_value = []  # No issues

        result = generate_release_notes(mock_context)

        assert isinstance(result, Error)
        assert "No JIRA issues found" in result.message

    def test_generate_release_notes_success_without_ai(self, mock_context):
        """Test that step succeeds with fallback to original summaries when AI not available"""
        from titan_plugin_jira.steps.generate_release_notes_step import generate_release_notes
        from titan_cli.engine import Success

        # Mock issues
        issues = [{
            "key": "ECAPP-100",
            "fields": {
                "summary": "Test issue",
                "description": "Test description",
                "components": [{"name": "Mobile"}],
                "customfield_11931": [{"value": "Yoigo"}]
            }
        }]

        # Setup context
        def mock_get(key, default=None):
            if key == "issues":
                return issues
            elif key == "fix_version":
                return "26.4.0"
            return default

        mock_context.get.side_effect = mock_get
        mock_context.set = MagicMock()

        result = generate_release_notes(mock_context)

        # Should succeed
        assert isinstance(result, Success)

        # Should have stored data in context
        assert mock_context.set.called

        # Verify metadata
        assert result.metadata["fix_version"] == "26.4.0"
        assert result.metadata["total_issues"] == 1
