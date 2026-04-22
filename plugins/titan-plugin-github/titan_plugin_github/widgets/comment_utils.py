"""
Comment Body Utilities

Pure parsing and rendering of comment body text (markdown, code blocks, suggestions).

This module is responsible ONLY for:
  - Parsing comment body markdown (TextElement, CodeBlockElement, SuggestionElement)
  - Rendering parsed elements as Textual widgets
  - Extracting code lines for suggestion display

This module is NOT responsible for:
  - Diff parsing or interpretation (use DiffContextManager)
  - Determining outdated status (use ResolvedCommentContext)
  - Resolving line numbers or positions (use DiffContextManager)

Keep this separation strict to avoid logic creep back into the UI layer.
"""

import re
from dataclasses import dataclass
from typing import List, Union, Optional

from ..managers.diff_context_manager import build_focused_diff_from_hunk, extract_lines_from_hunk


@dataclass
class TextElement:
    """Plain text content from comment body."""
    content: str


@dataclass
class SuggestionElement:
    """Code suggestion block from comment body."""
    code: str
    original_lines: Optional[str] = None  # Can be multiple lines (multiline suggestions)
    start_line: Optional[int] = None  # Starting line number for the suggestion


@dataclass
class CodeBlockElement:
    """Code block from comment body."""
    code: str
    language: str


CommentElement = Union[TextElement, SuggestionElement, CodeBlockElement]

_HUNK_HEADER_RE = re.compile(r'@@ -\d+,?\d* \+(\d+),?\d* @@')


def parse_comment_body(
    body: str,
    diff_hunk: Optional[str] = None,
    line: Optional[int] = None
) -> List[CommentElement]:
    """
    Parse comment body into structured elements.

    Args:
        body: Comment body text (may contain markdown, code blocks, suggestions)
        diff_hunk: Diff context (used to extract original lines for suggestions)
        line: Line number being commented on

    Returns:
        List of parsed elements (TextElement, SuggestionElement, CodeBlockElement)
    """
    if not body or not body.strip():
        return []

    body = body.replace("\r\n", "\n")
    elements: List[CommentElement] = []

    code_block_pattern = re.compile(r"```(\w+)?\n(.*?)```", re.DOTALL)
    matches = list(code_block_pattern.finditer(body))

    if not matches:
        return [TextElement(content=body.strip())]

    last_end = 0
    for match in matches:
        text_before = body[last_end : match.start()].strip()
        if text_before:
            elements.append(TextElement(content=text_before))

        language = match.group(1) or "text"
        code = match.group(2).strip()

        if language == "suggestion":
            original_lines = None
            target_line = line

            if not target_line and diff_hunk:
                header_match = _HUNK_HEADER_RE.match(diff_hunk.split('\n')[0])
                if header_match:
                    target_line = int(header_match.group(1))

            if diff_hunk and target_line:
                num_lines = len(code.split('\n'))
                original_lines = extract_lines_from_hunk(diff_hunk, target_line, num_lines)

            elements.append(SuggestionElement(
                code=code,
                original_lines=original_lines,
                start_line=target_line
            ))
        else:
            elements.append(CodeBlockElement(code=code, language=language))

        last_end = match.end()

    text_after = body[last_end:].strip()
    if text_after:
        elements.append(TextElement(content=text_after))

    return elements


def render_comment_elements(body: str, diff_hunk: Optional[str] = None, line: Optional[int] = None):
    """
    Parse and render comment body into Textual widgets.

    Args:
        body: Comment body text
        diff_hunk: Diff context (for suggestions)
        line: Line number (for suggestions)

    Returns:
        List of Textual widgets ready to be yielded
    """
    from textual.widgets import Markdown
    from .code_block import CodeBlock

    if not body or not body.strip():
        return []

    elements = parse_comment_body(body=body, diff_hunk=diff_hunk, line=line)

    widgets = []
    for element in elements:
        if isinstance(element, TextElement):
            markdown_widget = Markdown(element.content)
            markdown_widget.styles.width = "100%"
            markdown_widget.styles.height = "auto"
            markdown_widget.styles.padding = (1, 1, 0, 1)
            widgets.append(markdown_widget)

        elif isinstance(element, SuggestionElement):
            code_widget = CodeBlock(
                code=element.code,
                language="suggestion",
                original_lines=element.original_lines,
                start_line=element.start_line or 1,
                theme="native",
                line_numbers=True,
            )
            widgets.append(code_widget)

        elif isinstance(element, CodeBlockElement):
            code_widget = CodeBlock(
                code=element.code,
                language=element.language,
                theme="native",
                line_numbers=True,
            )
            widgets.append(code_widget)

    return widgets


def extract_diff_context(
    diff_hunk: str,
    target_line: Optional[int],
    is_outdated: bool = False
) -> str:
    """
    Extract relevant diff lines around the comment.

    Delegates to DiffContextManager's internal helper. Kept here for
    backwards compatibility with comment_view and other callers.

    Args:
        diff_hunk: Diff hunk from GitHub API
        target_line: Line number being commented on
        is_outdated: Whether this is an outdated comment

    Returns:
        Trimmed diff with context (7 before + target + 3 after)
    """
    return build_focused_diff_from_hunk(diff_hunk, target_line, is_outdated)


__all__ = [
    "TextElement",
    "SuggestionElement",
    "CodeBlockElement",
    "CommentElement",
    "parse_comment_body",
    "render_comment_elements",
    "extract_diff_context",
]
