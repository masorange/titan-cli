"""
Operations for building the AI prompt that summarizes what a JIRA issue asks for.
"""

from typing import List, Tuple

from ..models.view import UIJiraComment, UIJiraIssue
from .plan_prompt_operations import format_jira_issue_context

ISSUE_SUMMARY_SYSTEM = (
    "You summarize Jira issues for the developer who will work on them. "
    "Write in the same language the issue is written in. Be brief and concrete: "
    "plain text, no preamble, no markdown headings, short lines."
)

ISSUE_SUMMARY_INSTRUCTIONS = """\
Summarize what this issue asks for, in three short parts, each starting on its own line with its label
(translated into the issue's language):

What: the goal in one or two sentences.
Criteria: what must be true when it is done, as "- " items; none stated -> say so.
Open questions: what is ambiguous or undecided, as "- " items; none -> say so.

Comments come after the description and may refine, correct or settle what it says:
when they do, the latest word wins, and the summary says what changed.

{context}
"""


def build_issue_summary_prompt(issue: UIJiraIssue, comments: List[UIJiraComment]) -> Tuple[str, str]:
    """
    The prompt and system prompt asking an AI what `issue` asks for, taking its
    comments into account (they may refine or overturn the description).
    """
    context = format_jira_issue_context(issue, comments)
    return ISSUE_SUMMARY_INSTRUCTIONS.format(context=context), ISSUE_SUMMARY_SYSTEM
