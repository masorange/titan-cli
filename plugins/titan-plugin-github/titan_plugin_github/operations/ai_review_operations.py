"""
Operations for the iterative AI code review feature.

Pure functions — no UI, no side effects. Each function takes plain data
and returns plain data. All prompt templates are defined here so they can
be tested and tuned independently of the steps that call them.
"""

from typing import List, Optional

from titan_cli.core.models.code_review import ReviewFinding
from titan_cli.core.validators.markdown_parser import (
    parse_initial_review_markdown,
    parse_refined_suggestion,
)

from ..models.view import UICommentThread, UIPullRequest


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
