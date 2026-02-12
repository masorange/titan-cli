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


def extract_diff_context(
    diff_hunk: str,
    target_line: Optional[int],
    is_outdated: bool = False
) -> str:
    """
    Extract relevant diff lines around the comment, following Microsoft's approach.

    Args:
        diff_hunk: Diff hunk from GitHub API
        target_line: Line number being commented on
        is_outdated: Whether this is an outdated comment

    Returns:
        Diff with relevant context (7 before + target + 3 after), or full diff if extraction fails
    """
    if not diff_hunk:
        return ""

    lines = diff_hunk.split('\n')
    if not lines:
        return diff_hunk

    # Parse the diff header
    header_match = re.match(r'@@ -(\d+),?(\d*) \+(\d+),?(\d*) @@(.*)', lines[0])
    if not header_match:
        return diff_hunk

    old_start = int(header_match.group(1))
    new_start = int(header_match.group(3))
    header_suffix = header_match.group(5)

    # Track line numbers as we parse (like Microsoft's parseDiffHunk)
    old_line = old_start
    new_line = new_start

    # Build list of (old_line, new_line, raw_line, index)
    parsed_lines = []
    for idx, raw_line in enumerate(lines[1:], start=1):
        if raw_line.startswith('+'):
            # Added line: only new_line increments
            parsed_lines.append((None, new_line, raw_line, idx))
            new_line += 1
        elif raw_line.startswith('-'):
            # Removed line: only old_line increments
            parsed_lines.append((old_line, None, raw_line, idx))
            old_line += 1
        elif raw_line.startswith(' '):
            # Context line: both increment
            parsed_lines.append((old_line, new_line, raw_line, idx))
            old_line += 1
            new_line += 1
        else:
            # Control line or empty
            parsed_lines.append((None, None, raw_line, idx))

    # Find target line in diff (only for non-outdated comments)
    target_idx = None
    if not is_outdated and target_line:
        for old_num, new_num, raw_line, idx in parsed_lines:
            if new_num == target_line:
                target_idx = idx
                break

    # Decide which lines to extract
    if target_idx is not None:
        # Target found: extract context around it (7 before + target + 3 after)
        min_idx = max(0, target_idx - 7)
        max_idx = min(len(parsed_lines) - 1, target_idx + 3)
        extracted = parsed_lines[min_idx:max_idx + 1]
    elif len(parsed_lines) > 10:
        # Target not found or outdated with large diff: show last 10 lines
        extracted = parsed_lines[-10:]
    else:
        # Small diff: show all
        return diff_hunk

    # Rebuild diff with extracted lines
    return _rebuild_diff(extracted, old_start, new_start, header_suffix)


def _rebuild_diff(extracted_lines, old_start, new_start, header_suffix):
    """Rebuild a diff from extracted lines with correct header."""
    # Find start lines for the extracted portion
    extracted_new_start = None
    extracted_old_start = None

    for old_num, new_num, raw_line, _ in extracted_lines:
        if extracted_new_start is None and new_num is not None:
            extracted_new_start = new_num
        if extracted_old_start is None and old_num is not None:
            extracted_old_start = old_num
        if extracted_new_start and extracted_old_start:
            break

    # Fallback to original starts
    if extracted_new_start is None:
        extracted_new_start = new_start
    if extracted_old_start is None:
        extracted_old_start = old_start

    # Count lines for each side
    old_count = sum(1 for old_num, _, raw_line, _ in extracted_lines
                   if raw_line.startswith('-') or raw_line.startswith(' '))
    new_count = sum(1 for _, new_num, raw_line, _ in extracted_lines
                   if raw_line.startswith('+') or raw_line.startswith(' '))

    # Build new header
    new_header = f"@@ -{extracted_old_start},{old_count} +{extracted_new_start},{new_count} @@{header_suffix}"

    # Extract raw lines
    extracted_raw_lines = [raw_line for _, _, raw_line, _ in extracted_lines]

    return new_header + '\n' + '\n'.join(extracted_raw_lines)


__all__ = [
    "TextElement",
    "SuggestionElement",
    "CodeBlockElement",
    "CommentElement",
    "parse_comment_body",
    "render_comment_elements",
    "extract_diff_context",
]
