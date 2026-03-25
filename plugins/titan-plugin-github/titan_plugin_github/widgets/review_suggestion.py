"""
ReviewSuggestion Widget

Widget for displaying an AI-generated review suggestion.
Shows: severity badge, file path, line, diff context, and suggestion body.
"""

from typing import List, Any
from textual.app import ComposeResult
from textual.widget import Widget
from textual.containers import Horizontal
from ..models.view import UIReviewSuggestion
from titan_cli.ui.tui.widgets import DimText, ItalicText, Text
from .code_block import CodeBlock
from .comment_utils import extract_diff_context, render_comment_elements


class ReviewSuggestion(Widget):
    """
    Widget for displaying an AI-generated review suggestion.

    Shows: severity badge, file path, line number, diff context, and body.
    """

    DEFAULT_CSS = """
    ReviewSuggestion {
        width: 100%;
        height: auto;
        margin-bottom: 1;
    }

    ReviewSuggestion Horizontal {
        width: 100%;
        height: auto;
    }

    ReviewSuggestion .severity-badge {
        width: auto;
        height: auto;
        margin-bottom: 1;
    }

    ReviewSuggestion .critical {
        border: round $error;
        padding: 0 2;
    }

    ReviewSuggestion .improvement {
        border: round $warning;
        padding: 0 2;
    }

    ReviewSuggestion .suggestion {
        border: round $accent;
        padding: 0 2;
    }
    """

    def __init__(
        self,
        suggestion: UIReviewSuggestion,
        **kwargs
    ):
        """
        Initialize review suggestion widget.

        Args:
            suggestion: The UIReviewSuggestion to display
        """
        super().__init__(**kwargs)
        self.suggestion = suggestion

    def compose(self) -> ComposeResult:
        """Compose suggestion with full context."""
        # Severity badge
        badge_text = {
            "critical": "🔴 CRITICAL",
            "improvement": "🟡 IMPROVEMENT",
            "suggestion": "🔵 SUGGESTION",
        }.get(self.suggestion.severity, self.suggestion.severity.upper())

        badge = Text(badge_text)
        badge.add_class("severity-badge")
        badge.add_class(self.suggestion.severity)
        yield badge

        # File info (path and line)
        yield self._file_info_container()

        # Code context (if has diff_context)
        if self.suggestion.diff_context:
            yield self._code_context_widget()

        # Suggestion body (parsed for markdown, code blocks, etc.)
        if self.suggestion.body and self.suggestion.body.strip():
            yield Text("")
            for widget in self._parse_and_render_body():
                yield widget

    def _file_info_container(self) -> Horizontal:
        """Create container for file path and line info."""
        file_widget = ItalicText(f"{self.suggestion.file_path}")
        file_widget.styles.width = "auto"
        file_widget.styles.margin = (0, 1, 0, 0)

        line_info = f"Line {self.suggestion.line}" if self.suggestion.line else "General file comment"
        line_widget = DimText(line_info)
        line_widget.styles.width = "auto"

        container = Horizontal(file_widget, line_widget)
        container.styles.height = "auto"
        container.styles.margin = (0, 0, 1, 0)

        return container

    def _code_context_widget(self) -> CodeBlock:
        """Create code block with relevant diff context around the target line."""
        context_code = extract_diff_context(
            diff_hunk=self.suggestion.diff_context,
            target_line=self.suggestion.line,
        )
        code_block = CodeBlock(
            code=context_code,
            language="diff",
            theme="native",
            line_numbers=True,
        )
        return code_block

    def _parse_and_render_body(self) -> List[Any]:
        """Parse suggestion body and render as Textual widgets (markdown, code blocks, etc.)."""
        return render_comment_elements(
            body=self.suggestion.body,
            diff_hunk=self.suggestion.diff_context,
            line=self.suggestion.line
        )


__all__ = ["ReviewSuggestion"]
