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
    original_line: Optional[str] = None


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
            original_line = None
            if diff_hunk and line:
                original_line = _extract_line_from_diff(diff_hunk, line)

            elements.append(SuggestionElement(
                code=code,
                original_line=original_line
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


def _extract_line_from_diff(diff_hunk: str, target_line: int) -> Optional[str]:
    """
    Extract the specific line from diff_hunk that was commented on.

    Args:
        diff_hunk: Diff context string
        target_line: Line number to extract

    Returns:
        The content of the line (without diff markers), or None if not found
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

    # Find the line that matches target_line
    for line in lines[1:]:  # Skip @@ header
        if line.startswith('+'):
            # Added line
            if current_line == target_line:
                return line[1:]  # Remove '+' marker
            current_line += 1
        elif line.startswith(' '):
            # Context line
            if current_line == target_line:
                return line[1:]  # Remove ' ' marker
            current_line += 1
        # Removed lines (-) don't increment line counter

    return None


__all__ = [
    "TextElement",
    "SuggestionElement",
    "CodeBlockElement",
    "CommentElement",
    "parse_comment_body",
]
