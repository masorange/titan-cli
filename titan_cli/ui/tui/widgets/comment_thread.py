"""
CommentThread Widget

Widget for displaying PR/issue comment threads using PanelContainer.
"""

from typing import Callable, List, Any, Optional
from datetime import datetime
import re
from textual.app import ComposeResult
from textual.widgets import Markdown
from titan_plugin_github.models import PRComment
from .panel_container import PanelContainer
from .code_block import CodeBlock
from .text import BoldText, DimText, ItalicText, Text, DimItalicText
from .prompt_choice import PromptChoice, ChoiceOption
from textual.containers import Horizontal


class CommentThread(PanelContainer):
    """
    Widget for displaying a comment thread.

    Inherits from PanelContainer for consistent theming.
    Includes comment metadata, body, and optional action buttons.
    """

    DEFAULT_CSS = """
    CommentThread.reply {
        margin-left: 4;
    }

    CommentThread PromptChoice {
        margin: 0;
        padding: 0;
        background: transparent;
        border: none;
    }
    """

    def __init__(
        self,
        pr_comment: PRComment,
        thread_number: str = None,
        is_reply: bool = False,
        is_outdated: bool = False,
        replies: Optional[List[PRComment]] = None,
        options: Optional[List[ChoiceOption]] = None,
        on_select: Optional[Callable[[Any], None]] = None,
        **kwargs,
    ):
        """
        Initialize comment thread widget.

        Args:
            pr_comment: The PR comment to display (renders only its own data)
            thread_number: Thread number text (e.g., "Thread 1 of 8") - only for main comment
            is_reply: Whether this is a reply (indented)
            is_outdated: Whether comment is on outdated code
            replies: List of reply comments (only for main comment, replies don't have sub-replies)
            options: Optional list of action buttons (only for main comment)
            on_select: Callback for when an action button is selected
        """
        # Choose variant based on state
        if is_outdated:
            variant = "warning"
        elif is_reply:
            variant = "info"
        else:
            variant = "default"

        # Initialize PanelContainer with variant and title
        super().__init__(variant=variant, title=thread_number, **kwargs)

        self.pr_comment = pr_comment
        self.is_outdated = is_outdated
        self.replies = replies or []
        self.options = options or []
        self.on_select_callback = on_select

        if is_reply:
            self.add_class("reply")

    def compose(self) -> ComposeResult:
        """Compose comment content and action buttons."""
        # Author and date in one line
        yield self._metadata_container()
        yield Text("")

        # File info (if this comment has path info)
        file_info = self._file_info_container()
        if file_info:
            yield file_info

        # Code context (if this comment has diff_hunk)
        code_context = self._code_context_widget()
        if code_context:
            yield code_context

        # Comment body - parse and render text and code blocks separately
        if self.pr_comment.body and self.pr_comment.body.strip():
            for widget in self._parse_and_render_body():
                yield widget
        else:
            yield DimItalicText("Skipped comment")

        # Replies (if any)
        if self.replies:
            yield Text("")
            yield BoldText(
                f"💬 {len(self.replies)} repl{'y' if len(self.replies) == 1 else 'ies'}:"
            )
            for reply in self.replies:
                # Create nested CommentThread for each reply
                # Each reply renders only its own PRComment data
                reply_widget = CommentThread(
                    pr_comment=reply, is_reply=True, is_outdated=self.is_outdated
                )
                yield reply_widget

        # Action buttons (if provided) - reuse PromptChoice widget
        if self.options and self.on_select_callback:
            yield Text("")  # Empty line
            yield PromptChoice(
                question="What would you like to do?",
                options=self.options,
                on_select=self.on_select_callback,
            )

    def on_mount(self) -> None:
        """Scroll to show this comment thread fully after it's mounted."""
        # Use call_after_refresh to ensure all content is rendered first
        self.call_after_refresh(self._scroll_to_show_buttons)

    def _scroll_to_show_buttons(self) -> None:
        """Find main scroll container and scroll to end to show action buttons."""
        try:
            # Find the workflow-execution-panel (main scroll container)
            parent = self.parent
            while parent:
                if hasattr(parent, "id") and parent.id == "workflow-execution-panel":
                    # Scroll to end to show buttons
                    parent.scroll_end(animate=False)
                    break
                parent = parent.parent
        except Exception:
            pass

    def _metadata_container(self) -> Horizontal:
        """Create a container for author and date metadata."""
        # Format date to DD/MM/YYYY HH:mm:ss
        formatted_date = self.pr_comment.created_at
        try:
            # Try to parse the date string and reformat it
            date_obj = datetime.fromisoformat(
                str(self.pr_comment.created_at).replace("Z", "+00:00")
            )
            formatted_date = date_obj.strftime("%d/%m/%Y %H:%M:%S")
        except Exception:
            # If parsing fails, use as-is
            pass

        # Create widgets first
        author_name = self.pr_comment.user.login if self.pr_comment.user else "Unknown"
        author_widget = BoldText(f"{author_name}")
        author_widget.styles.width = "auto"

        date_text = f" • {formatted_date}"
        if self.is_outdated:
            date_text += " (outdated)"
        date_widget = DimText(date_text)
        date_widget.styles.width = "auto"

        # Create container with children
        container = Horizontal(author_widget, date_widget)
        container.styles.height = "auto"

        return container

    def _file_info_container(self) -> Horizontal:
        """Create a container for file path and line info (for review comments)."""
        if not self.pr_comment.path:
            return None

        file_widget = ItalicText(f"{self.pr_comment.path}")
        file_widget.styles.width = "auto"
        file_widget.styles.margin = (0, 1, 0, 0)

        line_info = (
            f"Line {self.pr_comment.line}"
            if self.pr_comment.line
            else "General file comment"
        )
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

        Returns list of widgets: Text for plain text, CodeBlock for code blocks.
        """
        body = self.pr_comment.body.strip()
        if not body:
            return []

        # Normalize line endings (GitHub may send \r\n)
        body = body.replace("\r\n", "\n")

        widgets = []

        # DEBUG: Show info about parsing
        widgets.append(DimText(f"[DEBUG] Body length: {len(body)} chars"))
        widgets.append(DimText(f"[DEBUG] First 100: {body[:100]}"))

        # Regex to match code blocks: ```language\ncode\n```
        # Pattern captures: (language, code)
        code_block_pattern = re.compile(r"```(\w+)?\n(.*?)```", re.DOTALL)

        matches = list(code_block_pattern.finditer(body))

        widgets.append(DimText(f"[DEBUG] Code blocks found: {len(matches)}"))

        # If no code blocks found, just render as markdown
        if not matches:
            markdown_widget = Markdown(body)
            markdown_widget.styles.width = "100%"
            markdown_widget.styles.height = "auto"
            markdown_widget.styles.margin = (1, 0)
            widgets.append(markdown_widget)
            return widgets

        last_end = 0
        for match in matches:
            # Text before this code block
            text_before = body[last_end : match.start()].strip()
            if text_before:
                # Use Markdown for text to preserve formatting (bold, links, etc.)
                markdown_widget = Markdown(text_before)
                markdown_widget.styles.width = "100%"
                markdown_widget.styles.height = "auto"
                markdown_widget.styles.margin = (0, 0, 1, 0)
                widgets.append(markdown_widget)

            # Code block
            language = match.group(1) or "text"  # Default to "text" if no language
            code = match.group(2).strip()

            # For "suggestion" blocks, extract original line from diff_hunk
            original_line = None
            if language == "suggestion":
                original_line = self._extract_commented_line_from_diff()
                # DEBUG: Show suggestion info
                widgets.append(DimText(f"[DEBUG] Suggestion code: {code[:80]}"))
                widgets.append(DimText(f"[DEBUG] Original line: {original_line[:80] if original_line else 'None'}"))

            code_widget = CodeBlock(
                code=code,
                language=language,
                original_line=original_line,  # CodeBlock handles suggestion diff creation
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
            markdown_widget.styles.margin = (0, 0, 1, 0)
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
        lines = diff_hunk.split("\n")

        # Parse the @@ header to get starting line number
        # Format: @@ -old_start,old_lines +new_start,new_lines @@
        header_match = re.match(r"@@ -\d+,?\d* \+(\d+),?\d* @@", lines[0])
        if not header_match:
            return None

        start_line = int(header_match.group(1))
        current_line = start_line

        # Find the line that matches target_line
        for line in lines[1:]:  # Skip @@ header
            if line.startswith("+"):
                # Added line
                if current_line == target_line:
                    # Found it! Return without the + prefix
                    return line[1:]
                current_line += 1
            elif line.startswith(" "):
                # Context line
                if current_line == target_line:
                    # Found it! Return without the space prefix
                    return line[1:]
                current_line += 1
            # Removed lines (-) don't increment line counter

        return None


__all__ = ["CommentThread"]
