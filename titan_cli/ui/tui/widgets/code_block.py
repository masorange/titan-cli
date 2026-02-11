"""
CodeBlock Widget

Reusable widget for displaying syntax-highlighted code blocks.
"""

from textual.widgets import Static
from rich.syntax import Syntax


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
        padding: 0;
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

        # For diffs, auto-detect starting line number from @@ header and remove it
        if language == "diff" and line_numbers:
            import re
            lines = code.split('\n')
            if lines:
                # Format: @@ -old_start,old_lines +new_start,new_lines @@
                header_match = re.match(r'@@ -\d+,?\d* \+(\d+),?\d* @@', lines[0])
                if header_match:
                    start_line = int(header_match.group(1))
                    # Remove the header line from the code
                    code = '\n'.join(lines[1:])

        # Create Rich Syntax object
        syntax = Syntax(
            code,
            lexer=language,
            theme=theme,
            line_numbers=line_numbers,
            word_wrap=word_wrap,
            indent_guides=indent_guides,
            start_line=start_line,
        )

        # For suggestions, use Rich.Syntax without line numbers (just diff markers)
        if self._is_suggestion and self._suggestion_data:
            # Use Rich.Syntax for proper syntax highlighting
            # The diff code is already prepared with - and + markers
            # No line numbers for suggestions - just the diff
            suggestion_syntax = Syntax(
                code,
                lexer="diff",
                theme=theme,
                line_numbers=False,  # No line numbers for suggestions
                word_wrap=word_wrap,
                indent_guides=indent_guides,
                start_line=1,  # Start at 1 since we're not showing numbers anyway
            )
            super().__init__(suggestion_syntax, **kwargs)
        else:
            # Initialize Static with the syntax object
            super().__init__(syntax, **kwargs)


__all__ = ["CodeBlock"]
