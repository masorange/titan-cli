"""
ReviewSuggestion Widget

Widget for displaying an AI-generated review suggestion.
Shows: severity badge, file path, line, diff context, and suggestion body.
"""

from textual.app import ComposeResult
from textual.widget import Widget
from textual.containers import Horizontal
from ..models.view import UIReviewSuggestion
from titan_cli.ui.tui.widgets import DimText, ItalicText, Text
from .code_block import CodeBlock


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

        # Suggestion body
        if self.suggestion.body and self.suggestion.body.strip():
            yield Text("")
            yield Text(self.suggestion.body)

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
        """Create code block with syntax-highlighted diff context."""
        code_block = CodeBlock(
            code=self.suggestion.diff_context,
            language="diff",
            theme="native",
            line_numbers=True,
        )
        return code_block


__all__ = ["ReviewSuggestion"]
