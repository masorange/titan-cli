"""
Heuristic Markdown parser for AI-generated code review output.

Designed to be lax: AI output is non-deterministic so the parser
tries multiple patterns before giving up. It never raises — it returns
empty collections or None on failure.
"""

import re
from typing import List, Optional

from titan_cli.core.models.code_review import ReviewFinding, ReviewSeverity


# ── Severity detection ────────────────────────────────────────────────────────

_EMOJI_TO_SEVERITY = {
    "🔴": ReviewSeverity.CRITICAL,
    "🟡": ReviewSeverity.HIGH,
    "🟢": ReviewSeverity.MEDIUM,
    "🟠": ReviewSeverity.LOW,
}

_KEYWORD_TO_SEVERITY = {
    "critical": ReviewSeverity.CRITICAL,
    "high": ReviewSeverity.HIGH,
    "medium": ReviewSeverity.MEDIUM,
    "low": ReviewSeverity.LOW,
}


def extract_severity(text: str) -> ReviewSeverity:
    """
    Detect severity from a heading line like '### 🔴 CRITICAL: Title'.

    Falls back to HIGH if nothing matches.
    """
    for emoji, severity in _EMOJI_TO_SEVERITY.items():
        if emoji in text:
            return severity

    lower = text.lower()
    for keyword, severity in _KEYWORD_TO_SEVERITY.items():
        if keyword in lower:
            return severity

    return ReviewSeverity.HIGH


# ── Section extraction ────────────────────────────────────────────────────────

def extract_section(markdown: str, *heading_candidates: str) -> Optional[str]:
    """
    Extract the body of the first matching ## section.

    Args:
        markdown: Full markdown text.
        heading_candidates: One or more heading names to look for (case-insensitive).
            The section body ends at the next ## heading or end of string.

    Returns:
        Section body stripped of leading/trailing whitespace, or None if not found.
    """
    for heading in heading_candidates:
        pattern = rf"##\s+{re.escape(heading)}\s*\n(.*?)(?=\n##\s|\Z)"
        match = re.search(pattern, markdown, re.IGNORECASE | re.DOTALL)
        if match:
            return match.group(1).strip()
    return None


# ── Finding parser ────────────────────────────────────────────────────────────

# Matches headings like:
#   ### 🔴 CRITICAL: Missing validation
#   ### HIGH: Something wrong
#   ## 🟡 Medium issue
_FINDING_HEADING = re.compile(
    r"#{2,4}\s*"                             # ## or ### or ####
    r"(?:[🔴🟡🟢🟠⚪]\s*)?"               # optional emoji
    r"(?:CRITICAL|HIGH|MEDIUM|LOW)?\s*:?\s*" # optional severity keyword
    r"(.+)",                                 # title (capture group 1)
    re.IGNORECASE,
)

_FILE_LINE = re.compile(r"\*\*(?:File|Path)\*\*\s*:\s*`?([^`\n]+)`?(?:\s*:(\d+))?", re.IGNORECASE)
_PROBLEM_LINE = re.compile(r"\*\*(?:Problem|Issue|Description)\*\*\s*:\s*(.+)", re.IGNORECASE)
_SUGGESTION_LINE = re.compile(r"\*\*(?:Suggestion|Fix|Solution)\*\*\s*:\s*(.+)", re.IGNORECASE)


def _parse_finding_block(heading_line: str, body: str) -> ReviewFinding:
    """Parse a single finding block from its heading + body text."""
    severity = extract_severity(heading_line)

    title = re.sub(r"^[🔴🟡🟢🟠⚪\s]*(CRITICAL|HIGH|MEDIUM|LOW)?\s*:?\s*", "", heading_line, flags=re.IGNORECASE).strip()
    title = title or "Unnamed finding"

    file_match = _FILE_LINE.search(body)
    file_path = file_match.group(1).strip() if file_match else None
    line_number = int(file_match.group(2)) if file_match and file_match.group(2) else None

    problem_match = _PROBLEM_LINE.search(body)
    description = problem_match.group(1).strip() if problem_match else body.strip()[:200]

    suggestion_match = _SUGGESTION_LINE.search(body)
    suggestion = suggestion_match.group(1).strip() if suggestion_match else None

    return ReviewFinding(
        severity=severity,
        title=title,
        description=description,
        file=file_path,
        line=line_number,
        suggestion=suggestion,
    )


def parse_initial_review_markdown(markdown: str) -> List[ReviewFinding]:
    """
    Parse a full initial review Markdown response into ReviewFinding objects.

    Strategy:
    1. Look for a '## Findings' section and parse within it.
    2. Fall back to scanning the whole document for severity-tagged headings.

    Returns an empty list if nothing can be parsed — never raises.
    """
    if not markdown or not markdown.strip():
        return []

    findings_body = extract_section(markdown, "Findings", "Issues", "Comments", "Review") or markdown

    findings: List[ReviewFinding] = []
    blocks = re.split(r"\n(?=#{2,4}\s)", findings_body)

    for block in blocks:
        lines = block.strip().splitlines()
        if not lines:
            continue

        heading = lines[0].lstrip("#").strip()
        body = "\n".join(lines[1:])

        has_severity = any(k in heading.lower() for k in _KEYWORD_TO_SEVERITY) or \
                       any(e in heading for e in _EMOJI_TO_SEVERITY)

        if not has_severity:
            continue

        try:
            findings.append(_parse_finding_block(heading, body))
        except Exception:
            continue

    return findings


# ── Refinement response parser ────────────────────────────────────────────────

def parse_refined_suggestion(markdown: str) -> str:
    """
    Extract the usable reply text from an AI refinement response.

    Strips common meta-prefixes and returns clean text. If no specific
    section is found, returns the whole response trimmed.
    """
    if not markdown or not markdown.strip():
        return ""

    for candidate in ("Draft Reply", "Reply", "Response", "Suggestion"):
        section = extract_section(markdown, candidate)
        if section:
            return section

    lines = markdown.strip().splitlines()
    cleaned: List[str] = []
    skip_patterns = re.compile(
        r"^(here('s| is)|based on|incorporat|taking into account|sure[,!]?|of course[,!]?)",
        re.IGNORECASE,
    )
    for line in lines:
        if cleaned or not skip_patterns.match(line.strip()):
            cleaned.append(line)

    return "\n".join(cleaned).strip() or markdown.strip()
