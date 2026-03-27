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
