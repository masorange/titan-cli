"""
Ruff Operations

Pure business logic for ruff linter functionality.
These functions can be used by any step and are easily testable.
"""

import json
from pathlib import Path
from typing import List, Dict, Tuple


def parse_ruff_json_output(stdout: str) -> List[Dict]:
    """
    Parse ruff JSON output into list of errors.

    Args:
        stdout: JSON output from ruff check command

    Returns:
        List of error dicts or empty list if parsing fails

    Examples:
        >>> parse_ruff_json_output('[]')
        []
        >>> parse_ruff_json_output('[{"code": "E501"}]')
        [{'code': 'E501'}]
    """
    if not stdout or not stdout.strip():
        return []

    try:
        return json.loads(stdout)
    except json.JSONDecodeError:
        return []


def format_file_path(file_path: str, project_root: str) -> str:
    """
    Format file path relative to project root if possible.

    Args:
        file_path: Absolute or relative file path
        project_root: Project root directory

    Returns:
        Relative path if possible, otherwise original path

    Examples:
        >>> format_file_path("/home/user/project/src/file.py", "/home/user/project")
        'src/file.py'
        >>> format_file_path("/other/path/file.py", "/home/user/project")
        '/other/path/file.py'
    """
    try:
        project_path = Path(project_root).resolve()
        file_path_obj = Path(file_path).resolve()
        if file_path_obj.is_relative_to(project_path):
            return str(file_path_obj.relative_to(project_path))
    except (ValueError, OSError):
        pass  # Keep original path if conversion fails
    return file_path


def build_ruff_error_table_data(
    errors: List[Dict],
    project_root: str
) -> Tuple[List[str], List[List[str]]]:
    """
    Build table headers and rows from ruff errors.

    Args:
        errors: List of ruff error dicts
        project_root: Project root for path formatting

    Returns:
        Tuple of (headers, rows)

    Examples:
        >>> errors = [{"filename": "/test.py", "location": {"row": 1, "column": 2}, "code": "E501", "message": "Line too long"}]
        >>> headers, rows = build_ruff_error_table_data(errors, "/")
        >>> headers
        ['File', 'Line', 'Col', 'Code', 'Message']
        >>> len(rows)
        1
    """
    headers = ["File", "Line", "Col", "Code", "Message"]
    rows = []

    for error in errors:
        file_path = format_file_path(error.get("filename", "Unknown file"), project_root)
        location = error.get("location", {})
        row = str(location.get("row", "?"))
        col = str(location.get("column", "?"))
        code = error.get("code", "")
        message = error.get("message", "")

        rows.append([file_path, row, col, code, message])

    return headers, rows


def format_ruff_errors_for_ai(errors: List[Dict], project_root: str) -> str:
    """
    Format ruff errors as text for AI consumption.

    Args:
        errors: List of ruff error dicts
        project_root: Project root for path formatting

    Returns:
        Formatted text with error details

    Examples:
        >>> errors = [{"filename": "/test.py", "location": {"row": 1, "column": 2}, "code": "E501", "message": "Too long", "url": "http://example.com"}]
        >>> result = format_ruff_errors_for_ai(errors, "/")
        >>> "test.py:1:2" in result
        True
    """
    errors_text = f"{len(errors)} linting issues found:\n\n"

    for error in errors:
        file_path = format_file_path(error.get("filename", "Unknown file"), project_root)
        location = error.get("location", {})

        errors_text += f"• {file_path}:{location.get('row', '?')}:{location.get('column', '?')} - [{error.get('code', '')}] {error.get('message', '')}\n"

        if error.get("url"):
            errors_text += f"  Docs: {error['url']}\n"

    return errors_text


__all__ = [
    "parse_ruff_json_output",
    "format_file_path",
    "build_ruff_error_table_data",
    "format_ruff_errors_for_ai",
]
