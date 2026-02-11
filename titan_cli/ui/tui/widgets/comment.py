"""
Comment Widget

Widget for displaying the main comment in a review thread.
Shows: author, date, file path, line, diff context, and comment body.
"""

from typing import List, Any, Optional
from textual.app import ComposeResult
from textual.widgets import Markdown
from textual.widget import Widget
from textual.containers import Horizontal
from titan_cli.ui.tui.models import UIComment
from .code_block import CodeBlock
from .text import BoldText, DimText, ItalicText, Text, DimItalicText
from .comment_utils import parse_comment_body, TextElement, SuggestionElement, CodeBlockElement


class Comment(Widget):
    """
    Widget for displaying the main comment in a review thread.

    Shows all context: author, date, file path, line number, diff hunk, and body.
    For replies, use ReplyComment widget instead.
    """

    DEFAULT_CSS = """
    Comment {
        width: 100%;
        height: auto;
    }

    Comment Horizontal {
        width: 100%;
        height: auto;
    }

    Comment .outdated-badge {
        border: round $warning;
        padding: 0 2;
        width: auto;
        height: auto;
        margin-bottom: 1;
    }
    """

    def __init__(
        self,
        comment: UIComment,
        is_outdated: bool = False,
        **kwargs
    ):
        """
        Initialize main comment widget.

        Args:
            comment: The UI comment to display
            is_outdated: Whether the thread is on outdated code
        """
        super().__init__(**kwargs)
        self.comment = comment
        self.is_outdated = is_outdated

    def compose(self) -> ComposeResult:
        """Compose main comment with full context."""
        # Outdated badge (if applicable) - shown first as visual indicator
        if self.is_outdated:
            badge = Text("Outdated")
            badge.add_class("outdated-badge")
            yield badge

        # Author and date
        yield self._metadata_container()
        yield Text("")

        # File info (if review comment)
        if self.comment.path:
            yield self._file_info_container()

        # Code context (if has diff_hunk)
        if self.comment.diff_hunk:
            yield self._code_context_widget()

        # Comment body
        if self.comment.body and self.comment.body.strip():
            for widget in self._parse_and_render_body():
                yield widget
        else:
            yield DimItalicText("(empty comment)")

    def _metadata_container(self) -> Horizontal:
        """Create container for author and date metadata."""
        # Author and date widgets (already formatted in UIComment)
        author_widget = BoldText(f"{self.comment.author_name}")
        author_widget.styles.width = "auto"

        date_widget = DimText(f" • {self.comment.formatted_date}")
        date_widget.styles.width = "auto"

        # Container
        container = Horizontal(author_widget, date_widget)
        container.styles.height = "auto"

        return container

    def _file_info_container(self) -> Horizontal:
        """Create container for file path and line info (only for main comments)."""
        file_widget = ItalicText(f"{self.comment.path}")
        file_widget.styles.width = "auto"
        file_widget.styles.margin = (0, 1, 0, 0)

        line_info = f"Line {self.comment.line}" if self.comment.line else "General file comment"
        line_widget = DimText(line_info)
        line_widget.styles.width = "auto"

        container = Horizontal(file_widget, line_widget)
        container.styles.height = "auto"
        container.styles.margin = (0, 0, 1, 0)

        return container

    def _code_context_widget(self) -> CodeBlock:
        """Create code block with syntax-highlighted diff context (only for main comments)."""
        # Show full diff for outdated comments or extract context for current ones
        context_code = self._extract_diff_context(
            diff_hunk=self.comment.diff_hunk,
            target_line=self.comment.line,
            is_outdated=self.is_outdated
        )

        code_block = CodeBlock(
            code=context_code,
            language="diff",
            theme="native",
            line_numbers=True,
        )

        return code_block

    def _extract_diff_context(
        self,
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
            Diff with relevant context, or full diff if extraction fails
        """
        if not diff_hunk:
            return ""

        import re

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

        # For outdated comments with large diffs, show last 10 lines (like Microsoft's slice(-maxLines))
        if is_outdated:
            if len(parsed_lines) > 10:
                # Show last 10 diff lines
                extracted = parsed_lines[-10:]

                # Find start lines for header
                extracted_new_start = None
                extracted_old_start = None
                for old_num, new_num, raw_line, _ in extracted:
                    if extracted_new_start is None and new_num is not None:
                        extracted_new_start = new_num
                    if extracted_old_start is None and old_num is not None:
                        extracted_old_start = old_num
                    if extracted_new_start and extracted_old_start:
                        break

                if extracted_new_start is None:
                    extracted_new_start = new_start
                if extracted_old_start is None:
                    extracted_old_start = old_start

                # Count lines for header
                old_count = sum(1 for old_num, _, raw_line, _ in extracted
                               if raw_line.startswith('-') or raw_line.startswith(' '))
                new_count = sum(1 for _, new_num, raw_line, _ in extracted
                               if raw_line.startswith('+') or raw_line.startswith(' '))

                # Rebuild diff with correct header
                new_header = f"@@ -{extracted_old_start},{old_count} +{extracted_new_start},{new_count} @@{header_suffix}"
                extracted_raw_lines = [raw_line for _, _, raw_line, _ in extracted]

                return new_header + '\n' + '\n'.join(extracted_raw_lines)
            else:
                return diff_hunk

        if not target_line:
            return diff_hunk

        # Find the line that matches target_line
        target_idx = None
        for old_num, new_num, raw_line, idx in parsed_lines:
            if new_num == target_line:
                target_idx = idx
                break

        if target_idx is None:
            # Target line not in diff, show full diff
            return diff_hunk

        # Extract last 8 lines before target + target + 3 after (like Microsoft's maxLines=8)
        context_before = 7
        context_after = 3
        min_idx = max(0, target_idx - context_before)
        max_idx = min(len(parsed_lines) - 1, target_idx + context_after)

        # Get the extracted lines
        extracted = parsed_lines[min_idx:max_idx + 1]

        # Find the new start line for the header (first non-removed line)
        extracted_new_start = None
        extracted_old_start = None

        for old_num, new_num, raw_line, _ in extracted:
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

        # Count lines for the new header
        old_count = sum(1 for old_num, _, raw_line, _ in extracted
                       if raw_line.startswith('-') or raw_line.startswith(' '))
        new_count = sum(1 for _, new_num, raw_line, _ in extracted
                       if raw_line.startswith('+') or raw_line.startswith(' '))

        # Rebuild diff with correct header
        new_header = f"@@ -{extracted_old_start},{old_count} +{extracted_new_start},{new_count} @@{header_suffix}"
        extracted_raw_lines = [raw_line for _, _, raw_line, _ in extracted]

        return new_header + '\n' + '\n'.join(extracted_raw_lines)

    def _parse_and_render_body(self) -> List[Any]:
        """
        Parse comment body and render text and code blocks separately.

        Uses comment_utils.parse_comment_body() to parse, then converts
        elements to Textual widgets.

        Returns list of widgets: Markdown for text, CodeBlock for code.
        """
        body = self.comment.body.strip()
        if not body:
            return []

        # Parse comment body into structured elements
        elements = parse_comment_body(
            body=body,
            diff_hunk=self.comment.diff_hunk,
            line=self.comment.line
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
                # DEBUG: Show extraction details
                widgets.append(DimText("─── SUGGESTION DEBUG ───"))
                widgets.append(DimText(f"Comment line: {self.comment.line}"))
                widgets.append(DimText(f"start_line: {element.start_line}"))
                widgets.append(DimText(f"Suggestion has {len(element.code.split(chr(10)))} line(s)"))
                widgets.append(DimText(f"Original lines: {element.original_lines if element.original_lines else 'NONE'}"))
                if self.comment.diff_hunk:
                    import re
                    hunk_lines = self.comment.diff_hunk.split('\n')
                    # Parse header to see what line range the diff covers
                    header_match = re.match(r'@@ -(\d+),?(\d*) \+(\d+),?(\d*) @@', hunk_lines[0])
                    if header_match:
                        new_start = int(header_match.group(3))
                        new_count = int(header_match.group(4)) if header_match.group(4) else 1
                        widgets.append(DimText(f"Diff covers lines {new_start} to {new_start + new_count - 1}"))
                    widgets.append(DimText(f"Diff header: {hunk_lines[0][:80]}"))
                    widgets.append(DimText(f"Diff has {len(hunk_lines)} total lines"))
                else:
                    widgets.append(DimText("diff_hunk: NONE"))
                widgets.append(DimText("────────────────────────"))

                # Render suggestion as CodeBlock with original lines (can be multiline)
                # No line numbers for suggestions, just diff markers
                code_widget = CodeBlock(
                    code=element.code,
                    language="suggestion",
                    original_lines=element.original_lines,
                    start_line=element.start_line or 1,
                    theme="native",
                    line_numbers=False,  # No line numbers in suggestions
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


__all__ = ["Comment"]
