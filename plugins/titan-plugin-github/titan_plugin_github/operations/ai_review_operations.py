"""
Operations for the iterative AI code review feature.

Pure functions — no UI, no side effects. Each function takes plain data
and returns plain data. All prompt templates are defined here so they can
be tested and tuned independently of the steps that call them.
"""

from typing import List, Optional, Tuple
import re

from titan_cli.core.models.code_review import ReviewFinding, ReviewSeverity
from titan_cli.core.validators.markdown_parser import (
    parse_initial_review_markdown,
    parse_refined_suggestion,
)

from ..models.view import UICommentThread, UIPullRequest, UIReviewSuggestion


# ── Diff utilities ────────────────────────────────────────────────────────────

def build_diff_summary(diff: str, max_diff_chars: int = 8_000) -> str:
    """
    Build a concise summary of the diff for headless CLI consumption.

    Extracts file list with change counts, then includes a truncated diff.
    This reduces verbosity while preserving context.

    Args:
        diff: Full unified diff string
        max_diff_chars: Maximum characters to include from the diff

    Returns:
        A summary with file changes + limited diff content
    """
    if not diff or not diff.strip():
        return "(No diff available)"

    # Parse file headers and count changes per file
    file_stats: dict[str, tuple[int, int]] = {}  # {filename: (additions, deletions)}

    # Split diff into per-file sections
    file_blocks = re.split(r'^diff --git', diff, flags=re.MULTILINE)

    for block in file_blocks[1:]:  # Skip the first empty split
        # Extract filename from "a/path b/path" header
        header_match = re.match(r' a/(.+) b/(.+)\n', block)
        if not header_match:
            continue

        filename = header_match.group(2)
        # Count + and - lines (excluding ++ and -- which are file markers)
        additions = len(re.findall(r'\n\+(?!\+)', block))
        deletions = len(re.findall(r'\n-(?!-)', block))
        file_stats[filename] = (additions, deletions)

    # Build file summary
    file_summary_lines = []
    for filename, (adds, deletes) in sorted(file_stats.items()):
        file_summary_lines.append(f"  {filename}: +{adds} -{deletes}")

    file_summary = "## Files Changed\n" + "\n".join(file_summary_lines) if file_summary_lines else ""

    # Include truncated diff
    diff_truncated = diff[:max_diff_chars]
    if len(diff) > max_diff_chars:
        diff_truncated += f"\n\n... ({len(diff) - max_diff_chars} more characters truncated)"

    diff_section = f"## Diff\n\n```diff\n{diff_truncated}\n```"

    return (file_summary + "\n\n" + diff_section).strip() if file_summary else diff_section


# ── Prompt builders ───────────────────────────────────────────────────────────

def build_initial_review_prompt(
    pr: UIPullRequest,
    diff: str,
    comments: List[UICommentThread],
    project_instructions: Optional[str] = None,
) -> str:
    """
    Build the prompt for the first (automatic) AI analysis of a PR.

    Args:
        pr: Pull request UI model.
        diff: Full unified diff of the PR.
        comments: Existing open comment threads.
        project_instructions: Content of CLAUDE.md / GEMINI.md if available.

    Returns:
        Prompt string ready to be sent to the headless CLI.
    """
    sections: List[str] = []

    sections.append(
        f"You are an expert code reviewer. Analyze the following pull request "
        f"and report issues you find.\n\n"
        f"## PR #{pr.number} — {pr.title}\n"
        f"**Author**: {pr.author_name}\n"
        f"**Branches**: {pr.branch_info}\n"
        f"**Description**: {pr.body or '(none)'}"
    )

    if project_instructions:
        sections.append(f"## Project Guidelines\n\n{project_instructions[:4000]}")

    if comments:
        thread_lines: List[str] = []
        for i, thread in enumerate(comments, 1):
            c = thread.main_comment
            location = f"`{c.path}` line {c.line}" if c.path else "general"
            entry = f"### Thread {i} [comment_id:{c.id}]\n**{c.author_login}** on {location}:\n> {c.body}"
            if thread.replies:
                replies = "\n".join(f"- **{r.author_login}**: {r.body}" for r in thread.replies)
                entry += f"\n\n**Replies:**\n{replies}"
            thread_lines.append(entry)
        sections.append("## Existing Comments\n\n" + "\n\n".join(thread_lines))

    max_diff = 40_000
    diff_text = diff[:max_diff] + ("\n\n... (diff truncated)" if len(diff) > max_diff else "")
    sections.append(f"## Diff\n\n```diff\n{diff_text}\n```")

    sections.append(
        "## Instructions\n\n"
        "Identify issues related to security, correctness, performance, and maintainability.\n"
        "For each issue use this format:\n\n"
        "### 🔴 CRITICAL | 🟡 HIGH | 🟢 MEDIUM | 🟠 LOW: <title>\n"
        "**File**: `path/to/file.py`:line\n"
        "**Problem**: description\n"
        "**Suggestion**: specific fix\n\n"
        "Start with a brief ## Summary section. Be direct and concise."
    )

    return "\n\n".join(sections)


def build_initial_review_prompt_headless(
    pr: UIPullRequest,
    diff: str,
    comments: List[UICommentThread],
    project_instructions: Optional[str] = None,
) -> str:
    """
    Build the prompt for headless CLI review (optimized for size).

    Uses a summarized diff instead of the full diff to reduce token usage
    and memory pressure on CLI tools (e.g., Gemini CLI with Node.js).

    Args:
        pr: Pull request UI model.
        diff: Full unified diff of the PR.
        comments: Existing open comment threads (limited to first 5).
        project_instructions: Content of CLAUDE.md / GEMINI.md if available.

    Returns:
        Optimized prompt string for headless CLI.
    """
    sections: List[str] = []

    sections.append(
        f"You are an expert code reviewer. Analyze the following pull request "
        f"and report issues you find.\n\n"
        f"## PR #{pr.number} — {pr.title}\n"
        f"**Author**: {pr.author_name}\n"
        f"**Branches**: {pr.branch_info}\n"
        f"**Description**: {pr.body or '(none)'}"
    )

    if project_instructions:
        sections.append(f"## Project Guidelines\n\n{project_instructions[:2000]}")

    # Limit comments to first 5 to keep prompt manageable
    comments_to_include = comments[:5]
    if comments_to_include:
        thread_lines: List[str] = []
        for i, thread in enumerate(comments_to_include, 1):
            c = thread.main_comment
            location = f"`{c.path}` line {c.line}" if c.path else "general"
            # Truncate comment body to 200 chars
            body_preview = (c.body[:200] + "...") if len(c.body) > 200 else c.body
            entry = f"### Thread {i} [comment_id:{c.id}]\n**{c.author_login}** on {location}:\n> {body_preview}"
            thread_lines.append(entry)

        if len(comments) > 5:
            thread_lines.append(f"... and {len(comments) - 5} more comment(s)")

        sections.append("## Existing Comments\n\n" + "\n\n".join(thread_lines))

    # Use summarized diff
    diff_summary = build_diff_summary(diff, max_diff_chars=8_000)
    sections.append(diff_summary)

    sections.append(
        "## Instructions\n\n"
        "Identify issues related to security, correctness, performance, and maintainability.\n"
        "For each issue use this format:\n\n"
        "### 🔴 CRITICAL | 🟡 HIGH | 🟢 MEDIUM | 🟠 LOW: <title>\n"
        "**File**: `path/to/file.py`:line\n"
        "**Problem**: description\n"
        "**Suggestion**: specific fix\n\n"
        "Start with a brief ## Summary section. Be direct and concise."
    )

    return "\n\n".join(sections)


def build_refinement_prompt(
    original_comment: str,
    existing_replies: List[str],
    diff_snippet: Optional[str],
    user_feedback: str,
    previous_suggestion: Optional[str] = None,
) -> str:
    """
    Build the prompt for regenerating a reply after user feedback.

    The prompt intentionally avoids meta-conversation: it asks the AI to
    produce the reply directly, not to discuss it.

    Args:
        original_comment: The PR comment being addressed.
        existing_replies: Replies already posted in the thread.
        diff_snippet: Relevant diff hunk for context (optional).
        user_feedback: Additional context provided by the user.
        previous_suggestion: The agent's previous suggestion (optional).

    Returns:
        Prompt string ready to be sent to the headless CLI.
    """
    sections: List[str] = []

    sections.append(
        "Generate a direct, professional reply to the following pull request comment. "
        "Do not explain your reasoning — output only the reply text."
    )

    sections.append(f"## Original Comment\n\n> {original_comment}")

    if existing_replies:
        replies_text = "\n".join(f"> {r}" for r in existing_replies)
        sections.append(f"## Thread Replies So Far\n\n{replies_text}")

    if diff_snippet:
        sections.append(f"## Relevant Diff\n\n```diff\n{diff_snippet}\n```")

    if previous_suggestion:
        sections.append(f"## Previous Draft Reply\n\n{previous_suggestion}")

    sections.append(
        f"## Additional Context from Reviewer\n\n{user_feedback}\n\n"
        "Incorporate the additional context above into an improved reply. "
        "Output only the reply — no preamble, no explanation."
    )

    return "\n\n".join(sections)


# ── Severity mapping ──────────────────────────────────────────────────────────

def _severity_to_ui(severity: ReviewSeverity) -> str:
    """Map ReviewSeverity enum to UIReviewSuggestion severity string."""
    match severity:
        case ReviewSeverity.CRITICAL:
            return "critical"
        case ReviewSeverity.HIGH | ReviewSeverity.MEDIUM:
            return "improvement"
        case ReviewSeverity.LOW:
            return "suggestion"
        case _:
            return "suggestion"


def parse_cli_review_output(markdown: str) -> Tuple[str, List[UIReviewSuggestion]]:
    """
    Parse CLI review markdown into a summary string and a list of suggestions.

    Args:
        markdown: Full markdown output from the headless CLI initial review.

    Returns:
        Tuple of (summary_markdown, suggestions) where summary_markdown is the
        ## Summary section text and suggestions is a list of UIReviewSuggestion
        objects built from the parsed findings.
    """
    # Extract summary: stop at the first ### finding heading, not just next ##
    summary_match = re.search(
        r"##\s+Summary\s*\n(.*?)(?=\n###\s|\n##\s|\Z)",
        markdown,
        re.IGNORECASE | re.DOTALL,
    )
    summary = summary_match.group(1).strip() if summary_match else ""

    findings = parse_initial_review_markdown(markdown)

    suggestions: List[UIReviewSuggestion] = []
    for finding in findings:
        suggestions.append(
            UIReviewSuggestion(
                file_path=finding.file or "",
                line=finding.line,
                body=f"**{finding.title}**\n\n{finding.description}\n\n{finding.suggestion or ''}".strip(),
                severity=_severity_to_ui(finding.severity),
                diff_context=None,
                snippet=None,
            )
        )

    return summary, suggestions


# ── Parsers (thin wrappers that keep the operations layer self-contained) ─────

def parse_review_findings(markdown: str) -> List[ReviewFinding]:
    """
    Parse the initial review markdown into a list of ReviewFinding objects.

    Delegates to the core markdown parser. Exposed here so callers
    import from operations rather than from the core validator directly.
    """
    return parse_initial_review_markdown(markdown)


def parse_reply_suggestion(markdown: str) -> str:
    """
    Extract the clean reply text from an AI refinement response.

    Delegates to the core markdown parser.
    """
    return parse_refined_suggestion(markdown)
