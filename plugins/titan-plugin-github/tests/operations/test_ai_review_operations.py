"""
Tests for ai_review_operations.
"""

from titan_plugin_github.operations.ai_review_operations import parse_cli_review_output


def test_parse_cli_review_output_keeps_all_summary_subsections():
    markdown = """
## Summary

### OVERVIEW
This PR updates authentication and token refresh flow.

### AREAS TO PAY ATTENTION TO
- Auth middleware migration
- Token expiry edge cases

### RECOMMENDATION
💬 COMMENT: Validate rollout strategy before merge.

### 🔴 CRITICAL: Missing token validation
**File**: `auth.py`:42
**Problem**: Access token is trusted without signature verification.
**Suggestion**: Verify JWT signature before claims access.
"""

    summary, _ = parse_cli_review_output(markdown)

    assert "### OVERVIEW" in summary
    assert "### AREAS TO PAY ATTENTION TO" in summary
    assert "### RECOMMENDATION" in summary
    assert "### 🔴 CRITICAL" not in summary


def test_parse_cli_review_output_keeps_summary_when_no_findings():
    markdown = """
## Summary

### OVERVIEW
Small refactor with no behavioral changes.

### AREAS TO PAY ATTENTION TO
- None

### RECOMMENDATION
✅ APPROVE: Looks safe.
"""

    summary, suggestions = parse_cli_review_output(markdown)

    assert "### OVERVIEW" in summary
    assert "### AREAS TO PAY ATTENTION TO" in summary
    assert "### RECOMMENDATION" in summary
    assert suggestions == []


def test_parse_cli_review_output_fallback_when_no_summary_header():
    """Test fallback extraction when AI doesn't include '## Summary' header."""
    markdown = """This PR updates authentication and token refresh flow. The changes look good overall.

## Issues Found

### 🔴 CRITICAL: Missing token validation
**File**: `auth.py`:42
**Problem**: Access token is trusted without signature verification.
**Suggestion**: Verify JWT signature before claims access.
"""

    summary, suggestions = parse_cli_review_output(markdown)

    # Should extract the initial paragraph as summary
    assert summary, "Summary should not be empty when initial content exists"
    assert "updates authentication" in summary
    # Should NOT include the finding header
    assert "🔴 CRITICAL" not in summary
    assert "## Issues Found" not in summary
    # Should have at least the critical finding
    critical_suggestions = [s for s in suggestions if s.severity == "critical" and s.file_path]
    assert len(critical_suggestions) >= 1
    assert critical_suggestions[0].file_path == "auth.py"


def test_parse_cli_review_output_extracts_findings_with_different_formats():
    """Test that findings are parsed correctly regardless of summary format."""
    markdown = """
No critical issues found. Code quality is good.

### 🟢 MEDIUM: Type hints could be improved
**File**: `utils.py`:10
**Problem**: Function signature lacks type hints.
**Suggestion**: Add type annotations for clarity.

### 🟠 LOW: Style improvement
**File**: `constants.py`:5
**Problem**: Inconsistent naming convention.
**Suggestion**: Rename to match style guide.
"""

    summary, suggestions = parse_cli_review_output(markdown)

    assert summary
    assert "No critical issues" in summary
    # Findings should not be in summary
    assert "🟢 MEDIUM" not in summary
    assert "🟠 LOW" not in summary
    # Should parse findings with proper file paths
    real_suggestions = [s for s in suggestions if s.file_path]
    assert len(real_suggestions) >= 2
    severities = [s.severity for s in real_suggestions]
    assert "improvement" in severities
    assert "suggestion" in severities
