"""
ReplyComment Widget

Widget for displaying reply comments in a review thread.
Shows only: author, date, and comment body (context already shown in main comment).
"""

from typing import List, Any
from textual.app import ComposeResult
from textual.widgets import Markdown
from textual.widget import Widget
from textual.containers import Horizontal
from titan_cli.ui.tui.models import UIComment
from .code_block import CodeBlock
from .text import BoldText, DimText, Text, DimItalicText
from .comment_utils import parse_comment_body, TextElement, SuggestionElement, CodeBlockElement


class ReplyComment(Widget):
    """
    Widget for displaying a reply comment in a review thread.

    Shows only author, date, and body - no file path, line, or diff context
    since those are already shown in the main comment.
    """

    DEFAULT_CSS = """
    ReplyComment {
        width: 100%;
        height: auto;
    }

    ReplyComment Horizontal {
        width: 100%;
    }
    """

    def __init__(self, reply: UIComment, **kwargs):
        """
        Initialize reply comment widget.

        Args:
            reply: The UI comment to display
        """
        super().__init__(**kwargs)
        self.reply = reply

    def compose(self) -> ComposeResult:
        """Compose reply comment (author + date + body only)."""
        # Author and date
        yield self._metadata_container()
        yield Text("")

        # Comment body (no file info or code context)
        if self.reply.body and self.reply.body.strip():
            for widget in self._parse_and_render_body():
                yield widget
        else:
            yield DimItalicText("(empty reply)")

    def _metadata_container(self) -> Horizontal:
        """Create container for author and date metadata."""
        author_widget = BoldText(f"{self.reply.author_name}")
        author_widget.styles.width = "auto"

        date_widget = DimText(f" • {self.reply.formatted_date}")
        date_widget.styles.width = "auto"

        container = Horizontal(author_widget, date_widget)
        container.styles.height = "auto"

        return container

    def _parse_and_render_body(self) -> List[Any]:
        """
        Parse reply body and render text and code blocks.

        Returns list of widgets: Markdown for text, CodeBlock for code.
        """
        body = self.reply.body.strip()
        if not body:
            return []

        # Parse comment body into structured elements
        # Replies can have suggestions too, so pass diff_hunk and line
        elements = parse_comment_body(
            body=body,
            diff_hunk=self.reply.diff_hunk,
            line=self.reply.line
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
                widgets.append(DimText("─── SUGGESTION DEBUG (REPLY) ───"))
                widgets.append(DimText(f"start_line: {element.start_line}"))
                widgets.append(DimText(f"Suggestion ({len(element.code.split(chr(10)))} lines): {element.code[:80]}"))
                widgets.append(DimText(f"Original lines: {element.original_lines if element.original_lines else 'NONE'}"))
                if self.reply.diff_hunk:
                    hunk_lines = self.reply.diff_hunk.split('\n')
                    widgets.append(DimText(f"Diff has {len(hunk_lines)} lines"))
                    widgets.append(DimText("First 5 lines of diff:"))
                    for i, line in enumerate(hunk_lines[:5]):
                        widgets.append(DimText(f"  [{i}] {line[:60]}"))
                else:
                    widgets.append(DimText("diff_hunk: NONE"))
                widgets.append(DimText(f"reply.line: {self.reply.line}"))
                widgets.append(DimText("────────────────────────────"))

                # Render suggestion as CodeBlock with original lines (can be multiline)
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


__all__ = ["ReplyComment"]
