"""
Tests for ai_review_operations.
"""

from titan_plugin_github.operations.ai_review_operations import parse_cli_review_output


def test_parse_cli_review_output_keeps_summary_content():
    markdown = """
## Summary

**Overview**: This PR updates authentication and token refresh flow.

**Attention**:
- Auth middleware migration
- Token expiry edge cases

**Recommendation**: COMMENT — Validate rollout strategy before merge.

## Issues Found

### CRITICAL: Missing token validation
**File**: `auth.py`:42
**Problem**: Access token is trusted without signature verification.
**Suggestion**: Verify JWT signature before claims access.
"""

    summary, suggestions = parse_cli_review_output(markdown)

    assert "**Overview**" in summary
    assert "**Attention**" in summary
    assert "**Recommendation**" in summary
    assert "CRITICAL" not in summary
    assert len(suggestions) == 1


def test_parse_cli_review_output_keeps_summary_when_no_findings():
    markdown = """
## Summary

**Overview**: Small refactor with no behavioral changes.

**Attention**:
- None

**Recommendation**: APPROVE — Looks safe.
"""

    summary, suggestions = parse_cli_review_output(markdown)

    assert "**Overview**" in summary
    assert "**Recommendation**" in summary
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


def test_parse_cli_review_output_claude_format_without_emojis():
    """Test Claude format without emojis — common case where Claude doesn't follow emoji format."""
    markdown = """## Summary

**Overview**: This PR introduces a headless CLI review feature with good structure overall.

**Recommendation**: APPROVE — No blocking issues.

## Issues Found

### CRITICAL: Missing JSON validation
**File**: `launcher.py`:42
**Problem**: Parsed output is not validated before use
**Suggestion**: Use json.loads with error handling

### HIGH - No timeout handling
**File**: `launcher.py`:80
**Problem**: Subprocess can hang indefinitely
**Suggestion**: Add timeout parameter to subprocess.run

### MEDIUM: Magic number
**Problem**: Hardcoded value 60 should be a named constant
**Suggestion**: Define DEFAULT_TIMEOUT = 60
"""

    summary, suggestions = parse_cli_review_output(markdown)

    # Summary should be extracted correctly even without emojis
    assert "Overview" in summary
    assert "CRITICAL" not in summary
    # Should find all three findings despite no emojis
    assert len(suggestions) == 3
    # Check severity mapping
    assert suggestions[0].severity == "critical"
    assert suggestions[0].file_path == "launcher.py"
    assert suggestions[1].severity == "improvement"
    assert suggestions[1].file_path == "launcher.py"
    assert suggestions[2].severity == "improvement"  # MEDIUM -> improvement


def test_parse_cli_review_output_lowercase_keywords():
    """Test that lowercase severity keywords are recognized."""
    markdown = """## Summary

Good PR with minor issues.

## Findings

### critical: Missing null check
**File**: `app.py`:15
**Problem**: Variable used without null safety
**Suggestion**: Add null guard

### high: Unsafe concatenation
**File**: `utils.py`:42
**Problem**: No input sanitization
**Suggestion**: Use safe string building
"""

    summary, suggestions = parse_cli_review_output(markdown)

    assert "Good PR with minor issues" in summary
    assert len(suggestions) == 2
    # Both should be parsed despite lowercase keyword
    assert suggestions[0].severity == "critical"
    assert suggestions[1].severity == "improvement"
