"""Tests for core.validators.markdown_parser."""

import unittest

from titan_cli.core.models.code_review import ReviewSeverity
from titan_cli.core.validators.markdown_parser import (
    extract_section,
    extract_severity,
    parse_initial_review_markdown,
    parse_refined_suggestion,
)

# ── Fixtures ──────────────────────────────────────────────────────────────────

MOCK_INITIAL_REVIEW = """
## Summary

PR introduces a headless AI CLI review feature.

## Findings

### 🔴 CRITICAL: Missing JSON validation
**File**: `launcher.py`:42
**Problem**: Parsed output is not validated before use
**Suggestion**: Use json.loads with error handling

### 🟡 HIGH: No timeout handling
**File**: `launcher.py`:80
**Problem**: Subprocess can hang indefinitely
**Suggestion**: Add timeout parameter to subprocess.run

### 🟢 MEDIUM: Magic number
**Problem**: Hardcoded value 60 should be a named constant
**Suggestion**: Define DEFAULT_TIMEOUT = 60

## Overall Risk

Medium — no critical security issues, but reliability could be improved.
"""

MOCK_NO_FINDINGS = """
## Summary

Everything looks good. No issues found.
"""

MOCK_REFINEMENT = """
Good point! If `use_pydantic: true` is set in the config, we should use it.
Will update the implementation accordingly.
"""

MOCK_REFINEMENT_WITH_SECTION = """
## Draft Reply

Thanks for the feedback. I'll add the timeout parameter — using 60s as default
which matches the existing behaviour in the rest of the codebase.
"""


# ── extract_severity ──────────────────────────────────────────────────────────

class TestExtractSeverity(unittest.TestCase):

    def test_emoji_critical(self):
        self.assertEqual(extract_severity("🔴 CRITICAL: Bad thing"), ReviewSeverity.CRITICAL)

    def test_emoji_high(self):
        self.assertEqual(extract_severity("🟡 HIGH: Slow query"), ReviewSeverity.HIGH)

    def test_emoji_medium(self):
        self.assertEqual(extract_severity("🟢 Medium: Minor issue"), ReviewSeverity.MEDIUM)

    def test_emoji_low(self):
        self.assertEqual(extract_severity("🟠 LOW: Nitpick"), ReviewSeverity.LOW)

    def test_keyword_only(self):
        self.assertEqual(extract_severity("CRITICAL: No emoji here"), ReviewSeverity.CRITICAL)

    def test_keyword_case_insensitive(self):
        self.assertEqual(extract_severity("high severity problem"), ReviewSeverity.HIGH)

    def test_unknown_defaults_to_high(self):
        self.assertEqual(extract_severity("Some heading without severity"), ReviewSeverity.HIGH)


# ── extract_section ───────────────────────────────────────────────────────────

class TestExtractSection(unittest.TestCase):

    def test_extracts_known_section(self):
        result = extract_section(MOCK_INITIAL_REVIEW, "Summary")
        self.assertIsNotNone(result)
        self.assertIn("headless", result)

    def test_returns_none_for_missing_section(self):
        result = extract_section(MOCK_INITIAL_REVIEW, "Nonexistent Section")
        self.assertIsNone(result)

    def test_case_insensitive(self):
        result = extract_section(MOCK_INITIAL_REVIEW, "summary")
        self.assertIsNotNone(result)

    def test_first_candidate_wins(self):
        result = extract_section(MOCK_INITIAL_REVIEW, "Summary", "Findings")
        self.assertIn("headless", result)

    def test_falls_back_to_second_candidate(self):
        result = extract_section(MOCK_INITIAL_REVIEW, "DoesNotExist", "Summary")
        self.assertIsNotNone(result)


# ── parse_initial_review_markdown ─────────────────────────────────────────────

class TestParseInitialReviewMarkdown(unittest.TestCase):

    def test_parses_three_findings(self):
        findings = parse_initial_review_markdown(MOCK_INITIAL_REVIEW)
        self.assertEqual(len(findings), 3)

    def test_first_finding_is_critical(self):
        findings = parse_initial_review_markdown(MOCK_INITIAL_REVIEW)
        self.assertEqual(findings[0].severity, ReviewSeverity.CRITICAL)

    def test_first_finding_has_file_and_line(self):
        findings = parse_initial_review_markdown(MOCK_INITIAL_REVIEW)
        self.assertEqual(findings[0].file, "launcher.py")
        self.assertEqual(findings[0].line, 42)

    def test_second_finding_is_high(self):
        findings = parse_initial_review_markdown(MOCK_INITIAL_REVIEW)
        self.assertEqual(findings[1].severity, ReviewSeverity.HIGH)

    def test_third_finding_has_no_file(self):
        findings = parse_initial_review_markdown(MOCK_INITIAL_REVIEW)
        self.assertIsNone(findings[2].file)

    def test_findings_have_descriptions(self):
        findings = parse_initial_review_markdown(MOCK_INITIAL_REVIEW)
        for f in findings:
            self.assertTrue(f.description)

    def test_empty_markdown_returns_empty_list(self):
        self.assertEqual(parse_initial_review_markdown(""), [])

    def test_no_findings_returns_empty_list(self):
        findings = parse_initial_review_markdown(MOCK_NO_FINDINGS)
        self.assertEqual(findings, [])

    def test_never_raises_on_garbage(self):
        try:
            parse_initial_review_markdown("# Not a review\nSome random text\n123")
        except Exception as e:
            self.fail(f"parse_initial_review_markdown raised: {e}")


# ── parse_refined_suggestion ──────────────────────────────────────────────────

class TestParseRefinedSuggestion(unittest.TestCase):

    def test_extracts_draft_reply_section(self):
        result = parse_refined_suggestion(MOCK_REFINEMENT_WITH_SECTION)
        self.assertIn("timeout parameter", result)
        self.assertNotIn("## Draft Reply", result)

    def test_falls_back_to_full_text_when_no_section(self):
        result = parse_refined_suggestion(MOCK_REFINEMENT)
        self.assertIn("use_pydantic", result)

    def test_strips_meta_preamble(self):
        text = "Sure! Here is my reply:\n\nActual content here."
        result = parse_refined_suggestion(text)
        self.assertIn("Actual content here", result)

    def test_empty_returns_empty_string(self):
        self.assertEqual(parse_refined_suggestion(""), "")

    def test_whitespace_only_returns_empty_string(self):
        self.assertEqual(parse_refined_suggestion("   \n\n  "), "")


if __name__ == "__main__":
    unittest.main()
