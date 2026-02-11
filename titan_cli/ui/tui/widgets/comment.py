"""
Comment Widget

Widget for displaying a single PR/issue comment.
"""

from typing import List, Any, Optional
from datetime import datetime
import re
from textual.app import ComposeResult
from textual.widgets import Markdown
from textual.widget import Widget
from textual.containers import Horizontal
from titan_plugin_github.models import PRComment
from .code_block import CodeBlock
from .text import BoldText, DimText, ItalicText, Text, DimItalicText


class Comment(Widget):
    """
    Widget for displaying a single comment.

    Renders all content from a PRComment:
    - Author and date metadata
    - File info (if review comment)
    - Code context (if has diff_hunk)
    - Comment body (text, code blocks, suggestions mixed)
    """

    DEFAULT_CSS = """
    Comment {
        width: 100%;
        height: auto;
    }
    """

    def __init__(
        self,
        pr_comment: PRComment,
        is_outdated: bool = False,
        **kwargs
    ):
        """
        Initialize comment widget.

        Args:
            pr_comment: The PR comment to display
            is_outdated: Whether comment is on outdated code
        """
        super().__init__(**kwargs)
        self.pr_comment = pr_comment
        self.is_outdated = is_outdated

    def compose(self) -> ComposeResult:
        """Compose comment content."""
        # Author and date
        yield self._metadata_container()
        yield Text("")

        # File info (if this is a review comment)
        file_info = self._file_info_container()
        if file_info:
            yield file_info

        # Code context (if has diff_hunk)
        code_context = self._code_context_widget()
        if code_context:
            yield code_context

        # Comment body - parse and render text and code blocks
        if self.pr_comment.body and self.pr_comment.body.strip():
            for widget in self._parse_and_render_body():
                yield widget
        else:
            yield DimItalicText("(empty comment)")

    def _metadata_container(self) -> Horizontal:
        """Create container for author and date metadata."""
        # Format date to DD/MM/YYYY HH:mm:SS
        formatted_date = self.pr_comment.created_at
        try:
            date_obj = datetime.fromisoformat(str(self.pr_comment.created_at).replace('Z', '+00:00'))
            formatted_date = date_obj.strftime("%d/%m/%Y %H:%M:%S")
        except Exception:
            pass

        # Author and date widgets
        author_name = self.pr_comment.user.login if self.pr_comment.user else "Unknown"
        author_widget = BoldText(f"{author_name}")
        author_widget.styles.width = "auto"

        date_text = f" • {formatted_date}"
        if self.is_outdated:
            date_text += " (outdated)"
        date_widget = DimText(date_text)
        date_widget.styles.width = "auto"

        # Container
        container = Horizontal(author_widget, date_widget)
        container.styles.height = "auto"

        return container

    def _file_info_container(self) -> Optional[Horizontal]:
        """Create container for file path and line info (for review comments)."""
        if not self.pr_comment.path:
            return None

        file_widget = ItalicText(f"{self.pr_comment.path}")
        file_widget.styles.width = "auto"
        file_widget.styles.margin = (0, 1, 0, 0)

        line_info = f"Line {self.pr_comment.line}" if self.pr_comment.line else "General file comment"
        line_widget = DimText(line_info)
        line_widget.styles.width = "auto"

        container = Horizontal(file_widget, line_widget)
        container.styles.height = "auto"
        container.styles.margin = (0, 0, 1, 0)

        return container

    def _code_context_widget(self) -> Optional[CodeBlock]:
        """Create code block widget with syntax-highlighted diff context."""
        if not self.pr_comment.diff_hunk:
            return None

        code_block = CodeBlock(
            code=self.pr_comment.diff_hunk,
            language="diff",
            theme="native",
            line_numbers=True,
        )

        return code_block

    def _parse_and_render_body(self) -> List[Any]:
        """
        Parse comment body and render text and code blocks separately.

        Returns list of widgets: Markdown for text, CodeBlock for code.
        """
        body = self.pr_comment.body.strip()
        if not body:
            return []

        # Normalize line endings (GitHub may send \r\n)
        body = body.replace("\r\n", "\n")

        widgets = []

        # Regex to match code blocks: ```language\ncode\n```
        code_block_pattern = re.compile(r"```(\w+)?\n(.*?)```", re.DOTALL)
        matches = list(code_block_pattern.finditer(body))

        # If no code blocks found, just render as markdown
        if not matches:
            markdown_widget = Markdown(body)
            markdown_widget.styles.width = "100%"
            markdown_widget.styles.height = "auto"
            markdown_widget.styles.padding = (1, 1, 0, 1)
            widgets.append(markdown_widget)
            return widgets

        last_end = 0
        for match in matches:
            # Text before this code block
            text_before = body[last_end : match.start()].strip()
            if text_before:
                markdown_widget = Markdown(text_before)
                markdown_widget.styles.width = "100%"
                markdown_widget.styles.height = "auto"
                markdown_widget.styles.padding = (1, 1, 0, 1)
                widgets.append(markdown_widget)

            # Code block
            language = match.group(1) or "text"
            code = match.group(2).strip()

            # For "suggestion" blocks, extract original line from diff_hunk
            original_line = None
            if language == "suggestion":
                original_line = self._extract_commented_line_from_diff()

            code_widget = CodeBlock(
                code=code,
                language=language,
                original_line=original_line,
                theme="native",
                line_numbers=True,
            )
            widgets.append(code_widget)

            last_end = match.end()

        # Text after last code block
        text_after = body[last_end:].strip()
        if text_after:
            markdown_widget = Markdown(text_after)
            markdown_widget.styles.width = "100%"
            markdown_widget.styles.height = "auto"
            markdown_widget.styles.padding = (1, 1, 0, 1)
            widgets.append(markdown_widget)

        return widgets

    def _extract_commented_line_from_diff(self) -> Optional[str]:
        """
        Extract the specific line from diff_hunk that was commented on.

        Returns:
            The content of the commented line (without diff markers), or None if not found
        """
        if not self.pr_comment.diff_hunk or not self.pr_comment.line:
            return None

        diff_hunk = self.pr_comment.diff_hunk
        target_line = self.pr_comment.line

        # Parse the diff hunk to find the line
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
                    return line[1:]
                current_line += 1
            elif line.startswith(' '):
                # Context line
                if current_line == target_line:
                    return line[1:]
                current_line += 1
            # Removed lines (-) don't increment line counter

        return None


__all__ = ["Comment"]
