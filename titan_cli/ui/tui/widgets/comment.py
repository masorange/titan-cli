"""
Comment Widget

Widget for displaying a single PR/issue comment.
"""

from typing import List, Any, Optional
from datetime import datetime
from textual.app import ComposeResult
from textual.widgets import Markdown
from textual.widget import Widget
from textual.containers import Horizontal
from titan_plugin_github.models import PRComment
from .code_block import CodeBlock
from .text import BoldText, DimText, ItalicText, Text, DimItalicText
from .comment_utils import parse_comment_body, TextElement, SuggestionElement, CodeBlockElement


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

    Comment Horizontal {
        width: 100%;
    }

    Comment .outdated-badge {
        color: $warning;
        border: round $warning;
        padding: 0 1;
        width: auto;
        height: auto;
        dock: right;
    }
    """

    def __init__(
        self,
        pr_comment: PRComment,
        is_outdated: bool = False,
        parent_comment: Optional[PRComment] = None,
        **kwargs
    ):
        """
        Initialize comment widget.

        Args:
            pr_comment: The PR comment to display
            is_outdated: Whether comment is on outdated code
            parent_comment: Parent comment (for replies, to compare diff_hunk)
        """
        super().__init__(**kwargs)
        self.pr_comment = pr_comment
        self.is_outdated = is_outdated
        self.parent_comment = parent_comment

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
        """Create container for author and date metadata with optional outdated badge."""
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

        date_widget = DimText(f" • {formatted_date}")
        date_widget.styles.width = "auto"

        # Build widgets list
        widgets = [author_widget, date_widget]

        # Add outdated badge if comment is outdated
        if self.is_outdated:
            badge = Text(" Outdated ")
            badge.add_class("outdated-badge")
            widgets.append(badge)

        # Container
        container = Horizontal(*widgets)
        container.styles.height = "auto"

        return container

    def _file_info_container(self) -> Optional[Horizontal]:
        """
        Create container for file path and line info (for review comments).

        For replies, only show if path/line differ from parent comment.
        """
        if not self.pr_comment.path:
            return None

        # If this is a reply with same file/line as parent, don't show redundant info
        if self.parent_comment is not None:
            parent_path = self.parent_comment.path
            parent_line = self.parent_comment.line

            # Skip if both path and line match parent
            if (parent_path == self.pr_comment.path and
                parent_line == self.pr_comment.line):
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
        """
        Create code block widget with syntax-highlighted diff context.

        For replies, only show diff_hunk if it's different from the parent comment.
        This prevents showing redundant code context in conversation threads.
        """
        if not self.pr_comment.diff_hunk:
            return None

        # If this is a reply, only show diff if it's different from parent
        if self.parent_comment is not None:
            parent_diff = self.parent_comment.diff_hunk
            # Skip if same diff_hunk as parent (redundant context)
            if parent_diff and parent_diff == self.pr_comment.diff_hunk:
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

        Uses comment_utils.parse_comment_body() to parse, then converts
        elements to Textual widgets.

        Returns list of widgets: Markdown for text, CodeBlock for code.
        """
        body = self.pr_comment.body.strip()
        if not body:
            return []

        # Parse comment body into structured elements
        elements = parse_comment_body(
            body=body,
            diff_hunk=self.pr_comment.diff_hunk,
            line=self.pr_comment.line
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
                # Render suggestion as CodeBlock with original line
                code_widget = CodeBlock(
                    code=element.code,
                    language="suggestion",
                    original_line=element.original_line,
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


__all__ = ["Comment"]
