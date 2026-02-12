"""
Comment Utilities

Utilities for parsing and processing PR/issue comment bodies.
"""

from dataclasses import dataclass
from typing import List, Union, Optional
import re


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


def parse_comment_body(
    body: str,
    diff_hunk: Optional[str] = None,
    line: Optional[int] = None
) -> List[CommentElement]:
    """
    Parse comment body into structured elements.

    Args:
        body: Comment body text (may contain markdown, code blocks, suggestions)
        diff_hunk: Diff context (used to extract original line for suggestions)
        line: Line number being commented on (used to extract original line)

    Returns:
        List of parsed elements (TextElement, SuggestionElement, CodeBlockElement)

    Example:
        >>> body = "Some text\\n```suggestion\\nfixed code\\n```\\nMore text"
        >>> elements = parse_comment_body(body, diff_hunk, 42)
        >>> # Returns: [TextElement("Some text"), SuggestionElement("fixed code", ...), TextElement("More text")]
    """
    if not body or not body.strip():
        return []

    # Normalize line endings
    body = body.replace("\r\n", "\n")

    elements: List[CommentElement] = []

    # Regex to match code blocks: ```language\ncode\n```
    code_block_pattern = re.compile(r"```(\w+)?\n(.*?)```", re.DOTALL)
    matches = list(code_block_pattern.finditer(body))

    # If no code blocks found, just return as single text element
    if not matches:
        return [TextElement(content=body.strip())]

    last_end = 0
    for match in matches:
        # Text before this code block
        text_before = body[last_end : match.start()].strip()
        if text_before:
            elements.append(TextElement(content=text_before))

        # Code block
        language = match.group(1) or "text"
        code = match.group(2).strip()

        # Handle suggestions specially
        if language == "suggestion":
            original_lines = None
            target_line = line

            # If line is None but we have diff_hunk, parse it from the @@ header
            if not target_line and diff_hunk:
                header_match = re.match(r'@@ -\d+,?\d* \+(\d+),?\d* @@', diff_hunk.split('\n')[0])
                if header_match:
                    target_line = int(header_match.group(1))

            if diff_hunk and target_line:
                # Count how many lines are in the suggestion
                num_lines = len(code.split('\n'))
                # Extract that many lines from diff_hunk starting at target line
                original_lines = _extract_lines_from_diff(diff_hunk, target_line, num_lines)

            elements.append(SuggestionElement(
                code=code,
                original_lines=original_lines,
                start_line=target_line
            ))
        else:
            # Regular code block
            elements.append(CodeBlockElement(
                code=code,
                language=language
            ))

        last_end = match.end()

    # Text after last code block
    text_after = body[last_end:].strip()
    if text_after:
        elements.append(TextElement(content=text_after))

    return elements


def _extract_lines_from_diff(diff_hunk: str, target_line: int, num_lines: int = 1) -> Optional[str]:
    """
    Extract multiple consecutive lines from diff_hunk for multiline suggestions.

    Args:
        diff_hunk: Diff context string
        target_line: Starting line number
        num_lines: Number of consecutive lines to extract

    Returns:
        The content of the lines (without diff markers), or None if not found
    """
    if not diff_hunk or not target_line:
        return None

    lines = diff_hunk.split('\n')

    # Parse the @@ header to get starting line number
    header_match = re.match(r'@@ -\d+,?\d* \+(\d+),?\d* @@', lines[0])
    if not header_match:
        return None

    start_line = int(header_match.group(1))
    current_line = start_line

    extracted_lines = []

    # Extract num_lines starting from target_line
    for line in lines[1:]:  # Skip @@ header
        if line.startswith('+'):
            # Added line
            if current_line >= target_line and len(extracted_lines) < num_lines:
                extracted_lines.append(line[1:])  # Remove '+' marker
            current_line += 1
        elif line.startswith(' '):
            # Context line
            if current_line >= target_line and len(extracted_lines) < num_lines:
                extracted_lines.append(line[1:])  # Remove ' ' marker
            current_line += 1
        # Removed lines (-) don't increment line counter

        # Stop when we have enough lines
        if len(extracted_lines) >= num_lines:
            break

    return '\n'.join(extracted_lines) if extracted_lines else None


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

    # Parse comment body into structured elements
    elements = parse_comment_body(
        body=body,
        diff_hunk=diff_hunk,
        line=line
    )

    # Convert elements to widgets
    widgets = []
    for element in elements:
        if isinstance(element, TextElement):
            # Render text as Markdown
            markdown_widget = Markdown(element.content)
            markdown_widget.styles.width = "100%"
            markdown_widget.styles.height = "auto"
            markdown_widget.styles.padding = (1, 1, 0, 1)
            widgets.append(markdown_widget)

        elif isinstance(element, SuggestionElement):
            # Render suggestion as CodeBlock with GitHub-style line numbers
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
            # Render code block
            code_widget = CodeBlock(
                code=element.code,
                language=element.language,
                theme="native",
                line_numbers=True,
            )
            widgets.append(code_widget)

    return widgets


__all__ = [
    "TextElement",
    "SuggestionElement",
    "CodeBlockElement",
    "CommentElement",
    "parse_comment_body",
    "render_comment_elements",
]
