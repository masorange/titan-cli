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
        original_line: str = None,
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
            original_line: For "suggestion" language, the original line to show in red
        """
        # Special handling for "suggestion" language (GitHub suggested changes)
        if language == "suggestion":
            if original_line:
                # Detect indentation from original line
                import re
                indent_match = re.match(r'^(\s*)', original_line)
                indent = indent_match.group(1) if indent_match else ""

                # Apply same indentation to suggestion if it doesn't have it
                if not code.startswith(indent):
                    code = indent + code.lstrip()

                # Create a diff showing original (red) and suggested (green)
                code = f"-{original_line}\n+{code}"
            else:
                # No original line, just show suggestion as added line
                code = f"+{code}"
            language = "diff"

        # Create Rich Syntax object
        syntax = Syntax(
            code,
            lexer=language,
            theme=theme,
            line_numbers=line_numbers,
            word_wrap=word_wrap,
            indent_guides=indent_guides,
        )

        # Initialize Static with the syntax object
        super().__init__(syntax, **kwargs)


__all__ = ["CodeBlock"]
