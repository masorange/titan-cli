"""
CommentView Widget

Unified widget for displaying a single comment with code context.

Handles three comment types seamlessly:
  - Inline review comments (has path + line + diff_hunk)
  - General PR comments (no code context → shows a "General PR comment" badge)
  - AI review suggestions (has severity badge, file path, diff context)

Does NOT include action buttons — that is the caller's responsibility.
"""

from typing import Any, List, Optional
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widget import Widget

from titan_cli.ui.tui.widgets import BoldText, DimText, ItalicText, Text, DimItalicText

from .code_block import CodeBlock
from .comment_utils import extract_diff_context, render_comment_elements


class CommentView(Widget):
    """
    Displays a single comment with its code context.

    Responsible for showing: author/date metadata, file location context,
    diff hunk, and the comment body (markdown, code blocks, suggestions).

    Action buttons are NOT part of this widget — mount them separately.
    """

    DEFAULT_CSS = """
    CommentView {
        width: 100%;
        height: auto;
    }

    CommentView Horizontal {
        width: 100%;
        height: auto;
    }

    CommentView .outdated-badge {
        border: round $warning;
        padding: 0 2;
        width: auto;
        height: auto;
        margin-bottom: 1;
    }

    CommentView .general-comment-badge {
        padding: 0 2;
        width: auto;
        height: auto;
        margin-bottom: 1;
        color: $text-muted;
    }

    CommentView .severity-badge {
        width: auto;
        height: auto;
        margin-bottom: 1;
    }

    CommentView .severity-badge.critical {
        border: round $error;
        padding: 0 2;
    }

    CommentView .severity-badge.improvement {
        border: round $warning;
        padding: 0 2;
    }

    CommentView .severity-badge.suggestion {
        border: round $accent;
        padding: 0 2;
    }
    """

    def __init__(
        self,
        body: str,
        author_name: str = "",
        formatted_date: str = "",
        file_path: Optional[str] = None,
        line: Optional[int] = None,
        diff_hunk: Optional[str] = None,
        severity: Optional[str] = None,
        is_outdated: bool = False,
        **kwargs,
    ):
        """
        Initialize the comment view.

        Args:
            body: Comment text body.
            author_name: Display name of the comment author.
            formatted_date: Pre-formatted date string (e.g. "27/03/2026 14:30").
            file_path: Path to the file this comment references (None for general comments).
            line: Line number in the file (None for general comments).
            diff_hunk: Diff context snippet around the commented line (None for general comments).
            severity: AI suggestion severity level ("critical", "improvement", "suggestion").
            is_outdated: Whether the comment references outdated code.
        """
        super().__init__(**kwargs)
        self.body = body
        self.author_name = author_name
        self.formatted_date = formatted_date
        self.file_path = file_path
        self.line = line
        self.diff_hunk = diff_hunk
        self.severity = severity
        self.is_outdated = is_outdated

    @classmethod
    def from_ui_comment(
        cls,
        comment: Any,
        is_outdated: bool = False,
    ) -> "CommentView":
        """
        Build a CommentView from a UIComment model.

        Args:
            comment: UIComment instance from the view layer.
            is_outdated: Whether the thread this comment belongs to is outdated.

        Returns:
            CommentView configured for the given comment type.
        """
        return cls(
            body=comment.body,
            author_name=comment.author_name,
            formatted_date=comment.formatted_date,
            file_path=comment.path,
            line=comment.line,
            diff_hunk=comment.diff_hunk,
            is_outdated=is_outdated,
        )

    @classmethod
    def from_suggestion(cls, suggestion: Any) -> "CommentView":
        """
        Build a CommentView from a UIReviewSuggestion model.

        Args:
            suggestion: UIReviewSuggestion instance from the AI review layer.

        Returns:
            CommentView configured to display the AI suggestion.
        """
        return cls(
            body=suggestion.body,
            file_path=suggestion.file_path,
            line=suggestion.line,
            diff_hunk=suggestion.diff_context,
            severity=suggestion.severity,
        )

    def compose(self) -> ComposeResult:
        """Compose the comment view: severity badge, metadata, location, code, body."""
        # 1. Severity badge (AI suggestions only)
        if self.severity:
            yield self._severity_badge()

        # 2. Author + date (omitted for AI suggestions that have no human author)
        if self.author_name:
            yield self._metadata_container()
            yield Text("")

        # 3. File/location context
        if self.file_path:
            # Inline review comment (has line) or file-level comment (no line)
            yield self._file_info_container()
            if self.is_outdated:
                yield self._outdated_badge()
        else:
            # No file path — this is a general PR comment (no file reference)
            yield self._general_comment_badge()

        # 4. Code context (only when diff_hunk is available AND there's a specific line)
        # File-level comments (path but no line) don't show diff — too verbose
        if self.diff_hunk and self.line:
            yield self._code_context_widget()

        # 5. Comment body
        if self.body and self.body.strip():
            for widget in self._parse_and_render_body():
                yield widget
        else:
            yield DimItalicText("(empty comment)")

    # ──────────────────────────────────────────────────────────────────────────
    # Private helpers
    # ──────────────────────────────────────────────────────────────────────────

    def _severity_badge(self) -> Text:
        """Create severity badge widget for AI suggestions."""
        badge_labels = {
            "critical": "🔴 CRITICAL",
            "improvement": "🟡 IMPROVEMENT",
            "suggestion": "🔵 SUGGESTION",
        }
        badge_text = badge_labels.get(self.severity, self.severity.upper())
        badge = Text(badge_text)
        badge.add_class("severity-badge")
        badge.add_class(self.severity)
        return badge

    def _metadata_container(self) -> Horizontal:
        """Create author + date row."""
        author_widget = BoldText(self.author_name)
        author_widget.styles.width = "auto"

        date_widget = DimText(f" • {self.formatted_date}")
        date_widget.styles.width = "auto"

        container = Horizontal(author_widget, date_widget)
        container.styles.height = "auto"
        return container

    def _file_info_container(self) -> Horizontal:
        """Create file path + line number row (inline review comments)."""
        file_widget = ItalicText(self.file_path)
        file_widget.styles.width = "auto"
        file_widget.styles.margin = (0, 1, 0, 0)

        if self.line:
            line_info = f"Line {self.line}"
        elif self.severity:
            # AI suggestion with file but no resolved line yet
            line_info = "General file comment"
        else:
            line_info = "General file comment"

        line_widget = DimText(line_info)
        line_widget.styles.width = "auto"

        container = Horizontal(file_widget, line_widget)
        container.styles.height = "auto"
        container.styles.margin = (0, 0, 1, 0)
        return container

    def _outdated_badge(self) -> Text:
        """Create outdated indicator for threads on stale code."""
        badge = Text("Outdated")
        badge.add_class("outdated-badge")
        return badge

    def _general_comment_badge(self) -> Text:
        """Create badge indicating this is a PR-level comment with no file reference."""
        badge = Text("💬 General PR comment")
        badge.add_class("general-comment-badge")
        return badge

    def _code_context_widget(self) -> CodeBlock:
        """Create syntax-highlighted diff block around the commented line."""
        context_code = extract_diff_context(
            diff_hunk=self.diff_hunk,
            target_line=self.line,
            is_outdated=self.is_outdated,
        )
        return CodeBlock(
            code=context_code,
            language="diff",
            theme="native",
            line_numbers=True,
        )

    def _parse_and_render_body(self) -> List[Any]:
        """Parse comment body and return Textual widgets for rendering."""
        return render_comment_elements(
            body=self.body,
            diff_hunk=self.diff_hunk,
            line=self.line,
        )


__all__ = ["CommentView"]
