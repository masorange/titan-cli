"""Shared formatting helpers for AI review prompts."""

import json
import re

from ..models.review_models import CommentContextEntry

_HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
_MD_IMAGE_RE = re.compile(r"!\[[^\]]*\]\([^)]*\)")
_HTML_IMAGE_RE = re.compile(r"<img\b[^>]*>", re.IGNORECASE)
_CHECKBOX_LINE_RE = re.compile(r"^\s*[-*]\s*\[[ xX]\]")
_BARE_LINK_LINE_RE = re.compile(
    r"^\s*!?\[[^\]]*\]\(https?://\S+\)\s*$|^\s*https?://\S+\s*$"
)


def extract_pr_intent(description: str, max_chars: int = 800) -> str:
    """
    Deterministically trim a PR description down to its reviewable intent.

    Strips HTML comments (template remnants), markdown images (memes/badges),
    checkbox lines, and bare-link lines; keeps prose and bullet text. Purely
    deterministic — never an AI call. Returns "" when nothing meaningful remains.
    """
    if not description:
        return ""

    text = _HTML_COMMENT_RE.sub("", description)
    text = _MD_IMAGE_RE.sub("", text)
    text = _HTML_IMAGE_RE.sub("", text)

    kept: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if _CHECKBOX_LINE_RE.match(line) or _BARE_LINK_LINE_RE.match(line):
            continue
        line = line.lstrip("#").strip()
        if line:
            kept.append(line)

    result = "\n".join(kept)
    return result[:max_chars].rstrip()


PR_DESCRIPTION_MAX_CHARS = 4000
"""How much of the author's description the review is handed, after the template is gone.

Whole in practice: ragnarok PR #3720's 2,752-char description is ~2,300 once cleaned. It
used to be ONE line -- the first long one, which in ragnarok's template is always the
heading "PR's Trigger (Check the VALIDITY of these links)" -- so the author's own ask,
"Verify that the deletions ... are properly covered by the new entries in
analytics_mapping.json", never reached the model, and neither did it find the dropped
events a free-form session found by reading the description. A one-call review pays for
this text once; the cap only stops a description written as a novel.
"""


def review_pr_description(description: str) -> str:
    """The author's description, stripped of template remnants, for the review prompts."""
    return extract_pr_intent(description, max_chars=PR_DESCRIPTION_MAX_CHARS)


def pr_description_section(description: str) -> str:
    """The description as its own prompt section, or "" when there is none."""
    if not description:
        return ""
    return (
        "\n## What the author says this PR does (and what they ask reviewers to check)\n"
        f"{description}\n"
    )


def comment_context_to_json(comments: list[CommentContextEntry]) -> str:
    """Serialize compact comment context entries for prompt embedding."""
    return json.dumps(
        [
            {
                "kind": entry.kind,
                "path": entry.path,
                "line": entry.line,
                "category": entry.category,
                "title": entry.title,
                "summary": entry.summary,
                "is_resolved": entry.is_resolved,
            }
            for entry in comments
        ],
        indent=2,
    )
