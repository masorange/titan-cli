"""
CodeBlock Widget

Reusable widget for displaying syntax-highlighted code blocks.
Uses centralized theme colors for consistency.
"""

from textual.widgets import Static
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text
import re

# Import theme colors for consistent styling
from titan_cli.ui.tui.colors import RichStyles


class CodeBlock(Static):
    """
    Widget for displaying syntax-highlighted code.

    Uses Rich.Syntax for high-quality syntax highlighting with many themes and languages.

    Example:
        code_block = CodeBlock(
            code="def hello():\n    print('world')",
            language="python",
            theme="monokai",
            line_numbers=True
        )
    """

    DEFAULT_CSS = """
    CodeBlock {
        width: 100%;
        height: auto;
        max-height: 25;
        overflow-y: auto;
        margin: 1 0;
        padding: 1;
        background: $surface;
    }
    """

    def __init__(
        self,
        code: str,
        language: str = "python",
        theme: str = "monokai",
        line_numbers: bool = False,
        word_wrap: bool = False,
        indent_guides: bool = False,
        original_lines: str = None,
        start_line: int = 1,
        **kwargs,
    ):
        """
        Initialize code block widget.

        Args:
            code: The code to display
            language: Programming language for syntax highlighting
                     (python, javascript, diff, suggestion, java, go, rust, etc.)
            theme: Color theme for syntax highlighting
                  (monokai, github-dark, dracula, vim, native, etc.)
            line_numbers: Whether to show line numbers
            word_wrap: Whether to wrap long lines
            indent_guides: Whether to show indent guides
            original_lines: For "suggestion" language, the original lines to show in red (can be multiline)
            start_line: Starting line number (for diffs with real line numbers)
        """
        # Special handling for "suggestion" language (GitHub suggested changes)
        self._is_suggestion = False
        self._suggestion_data = None

        if language == "suggestion":
            self._is_suggestion = True
            if original_lines:
                original_lines_list = original_lines.split('\n') if original_lines else []
                suggested_lines_list = code.split('\n')

                # Detect indentation from first original line
                import re
                indent = ""
                if original_lines_list:
                    indent_match = re.match(r'^(\s*)', original_lines_list[0])
                    indent = indent_match.group(1) if indent_match else ""

                # Apply same indentation to all suggested lines
                indented_suggested_lines = []
                for sugg_line in suggested_lines_list:
                    # Strip existing leading whitespace and apply original indent
                    stripped = sugg_line.lstrip()
                    indented_suggested_lines.append(indent + stripped)

                # Store suggestion data for custom rendering
                self._suggestion_data = {
                    'original_lines': original_lines_list,
                    'suggested_lines': indented_suggested_lines,
                    'start_line': start_line
                }

                # Create a diff showing original (red) and suggested (green)
                # All original lines with '-', then all suggested lines with '+'
                diff_lines = []
                for orig_line in original_lines_list:
                    diff_lines.append(f"-{orig_line}")
                for sugg_line in indented_suggested_lines:
                    diff_lines.append(f"+{sugg_line}")
                code = '\n'.join(diff_lines)
            else:
                # No original lines, just show suggestion as added lines
                suggested_lines_list = code.split('\n')
                self._suggestion_data = {
                    'original_lines': [],
                    'suggested_lines': suggested_lines_list,
                    'start_line': start_line
                }
                code = '\n'.join(f"+{line}" for line in suggested_lines_list)

            # For suggestions, disable line_numbers - we'll handle it specially in render
            language = "diff"
            line_numbers = False  # Disable Rich's line numbers for suggestions

        # Special handling for diffs with line numbers (GitHub-style)
        if language == "diff" and line_numbers and not self._is_suggestion:
            # Render diff manually with correct line numbers (old for -, new for +)
            renderable = self._render_diff_with_line_numbers(code, theme)
            super().__init__(renderable, **kwargs)
        elif self._is_suggestion and self._suggestion_data:
            # For suggestions, use GitHub-style rendering with line numbers
            if self._suggestion_data['original_lines']:
                # Has original lines - render with numbers
                renderable = self._render_suggestion_with_line_numbers(
                    self._suggestion_data['original_lines'],
                    self._suggestion_data['suggested_lines'],
                    self._suggestion_data['start_line'],
                    theme
                )
                super().__init__(renderable, **kwargs)
            else:
                # No original lines, just show suggestion as added lines without numbers
                suggestion_syntax = Syntax(
                    code,
                    lexer="diff",
                    theme=theme,
                    line_numbers=False,
                    word_wrap=word_wrap,
                    indent_guides=indent_guides,
                    start_line=1,
                )
                super().__init__(suggestion_syntax, **kwargs)
        else:
            # Regular code: auto-detect starting line for diffs without manual rendering
            if language == "diff":
                lines = code.split('\n')
                if lines:
                    header_match = re.match(r'@@ -\d+,?\d* \+(\d+),?\d* @@', lines[0])
                    if header_match:
                        start_line = int(header_match.group(1))
                        code = '\n'.join(lines[1:])

            # Create Rich Syntax object for normal rendering
            syntax = Syntax(
                code,
                lexer=language,
                theme=theme,
                line_numbers=line_numbers,
                word_wrap=word_wrap,
                indent_guides=indent_guides,
                start_line=start_line,
            )
            super().__init__(syntax, **kwargs)

    def _render_diff_with_line_numbers(self, code: str, theme: str):
        """
        Render a diff with GitHub-style line numbers (old for -, new for +).

        Returns a Rich Table with proper line numbering.
        """
        lines = code.split('\n')

        # Parse header to get starting line numbers
        header_match = re.match(r'@@ -(\d+),?\d* \+(\d+),?\d* @@', lines[0])
        if not header_match:
            # No valid header, fall back to Syntax
            return Syntax(code, lexer="diff", theme=theme, line_numbers=False)

        old_line = int(header_match.group(1))
        new_line = int(header_match.group(2))

        # Create table with line numbers and code
        table = Table(
            show_header=False,
            show_edge=False,
            padding=(0, 1, 0, 0),
            pad_edge=False,
            box=None,
            expand=True
        )
        table.add_column("line_num", width=6, justify="right", style="dim")
        table.add_column("marker", width=2)
        table.add_column("code", ratio=1)

        # Skip header, process diff lines
        for line in lines[1:]:
            if not line:
                # Empty line
                table.add_row("", "", "")
                continue

            marker = line[0] if line else ' '
            content = line[1:] if len(line) > 1 else ""

            if marker == '-':
                # Removed line: show old line number (theme red)
                line_num_text = Text(str(old_line), style=RichStyles.REMOVE_DIM)
                marker_text = Text("-", style=RichStyles.REMOVE_BOLD)
                content_text = Text(content, style=RichStyles.REMOVE)
                table.add_row(line_num_text, marker_text, content_text)
                old_line += 1
            elif marker == '+':
                # Added line: show new line number (theme green)
                line_num_text = Text(str(new_line), style=RichStyles.ADD_DIM)
                marker_text = Text("+", style=RichStyles.ADD_BOLD)
                content_text = Text(content, style=RichStyles.ADD)
                table.add_row(line_num_text, marker_text, content_text)
                new_line += 1
            elif marker == ' ':
                # Context line: both numbers match (theme muted)
                line_num_text = Text(str(new_line), style=RichStyles.CONTEXT_DIM)
                marker_text = Text(" ", style=RichStyles.CONTEXT_DIM)
                content_text = Text(content)
                table.add_row(line_num_text, marker_text, content_text)
                old_line += 1
                new_line += 1
            else:
                # Unknown line type, render as-is
                table.add_row("", "", Text(line))

        return table

    def _render_suggestion_with_line_numbers(
        self,
        original_lines: list,
        suggested_lines: list,
        start_line: int,
        theme: str
    ):
        """
        Render a suggestion with GitHub-style line numbers.

        Original lines get old line numbers, suggested lines get new line numbers.
        """
        table = Table(
            show_header=False,
            show_edge=False,
            padding=(0, 1, 0, 0),
            pad_edge=False,
            box=None,
            expand=True
        )
        table.add_column("line_num", width=6, justify="right", style="dim")
        table.add_column("marker", width=2)
        table.add_column("code", ratio=1)

        # Add original lines (removed) - theme red
        current_line = start_line
        for orig_line in original_lines:
            line_num_text = Text(str(current_line), style=RichStyles.REMOVE_DIM)
            marker_text = Text("-", style=RichStyles.REMOVE_BOLD)
            content_text = Text(orig_line, style=RichStyles.REMOVE)
            table.add_row(line_num_text, marker_text, content_text)
            current_line += 1

        # Add suggested lines (added) - theme green
        current_line = start_line
        for sugg_line in suggested_lines:
            line_num_text = Text(str(current_line), style=RichStyles.ADD_DIM)
            marker_text = Text("+", style=RichStyles.ADD_BOLD)
            content_text = Text(sugg_line, style=RichStyles.ADD)
            table.add_row(line_num_text, marker_text, content_text)
            current_line += 1

        return table


__all__ = ["CodeBlock"]
