"""
Comment Widget

Widget for displaying the main comment in a review thread.
Shows: author, date, file path, line, diff context, and comment body.
"""

from typing import List, Any
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
        code_block = CodeBlock(
            code=self.comment.diff_hunk,
            language="diff",
            theme="native",
            line_numbers=True,
        )

        return code_block

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
