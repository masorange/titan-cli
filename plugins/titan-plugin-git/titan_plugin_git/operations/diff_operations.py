"""
Diff Operations

Pure business logic for Git diff parsing and formatting.
These functions can be used by any step and are easily testable.
"""

from typing import List, Tuple


def parse_diff_stat_output(stat_output: str) -> Tuple[List[Tuple[str, str]], List[str]]:
    """
    Parse git diff --stat output into file lines and summary lines.

    Args:
        stat_output: Raw output from git diff --stat

    Returns:
        Tuple of (file_lines, summary_lines) where:
        - file_lines: List of (filename, stats) tuples
        - summary_lines: List of summary lines (e.g., "3 files changed, 10 insertions(+)")

    Examples:
        >>> output = "file.py | 5 ++---\\n 1 file changed, 2 insertions(+), 3 deletions(-)"
        >>> files, summary = parse_diff_stat_output(output)
        >>> files
        [('file.py', ' 5 ++---')]
        >>> summary
        [' 1 file changed, 2 insertions(+), 3 deletions(-)']
    """
    file_lines = []
    summary_lines = []

    for line in stat_output.split('\n'):
        if not line.strip():
            continue

        if '|' in line:
            # File line: "filename | stats"
            parts = line.split('|')
            filename = parts[0].strip()
            stats = '|'.join(parts[1:]) if len(parts) > 1 else ''
            file_lines.append((filename, stats))
        else:
            # Summary line: "3 files changed, 10 insertions(+), 5 deletions(-)"
            summary_lines.append(line)

    return file_lines, summary_lines


def get_max_filename_length(file_lines: List[Tuple[str, str]]) -> int:
    """
    Get the maximum filename length from parsed file lines for alignment.

    Args:
        file_lines: List of (filename, stats) tuples

    Returns:
        Maximum filename length (0 if no files)

    Examples:
        >>> files = [('short.py', ''), ('very_long_filename.py', '')]
        >>> get_max_filename_length(files)
        22
        >>> get_max_filename_length([])
        0
    """
    if not file_lines:
        return 0
    return max(len(filename) for filename, _ in file_lines)


def colorize_diff_stats(stats: str) -> str:
    """
    Colorize diff stats by replacing + and - with colored versions.

    Uses Rich markup format for colors.

    Args:
        stats: Stats string containing + and - characters

    Returns:
        Stats string with Rich color markup

    Examples:
        >>> colorize_diff_stats(" 5 ++---")
        ' 5 [green]+[/green][green]+[/green][red]-[/red][red]-[/red][red]-[/red]'
        >>> colorize_diff_stats(" 10 ++++++++++")
        ' 10 [green]+[/green][green]+[/green][green]+[/green][green]+[/green][green]+[/green][green]+[/green][green]+[/green][green]+[/green][green]+[/green][green]+[/green]'
        >>> colorize_diff_stats("no symbols")
        'no symbols'
    """
    colored = stats.replace('+', '[green]+[/green]')
    colored = colored.replace('-', '[red]-[/red]')
    return colored


def colorize_diff_summary(summary_line: str) -> str:
    """
    Colorize diff summary lines by adding color to (+) and (-) markers.

    Args:
        summary_line: Summary line like "3 files changed, 10 insertions(+), 5 deletions(-)"

    Returns:
        Summary line with Rich color markup

    Examples:
        >>> colorize_diff_summary("3 files changed, 10 insertions(+), 5 deletions(-)")
        '3 files changed, 10 insertions[green](+)[/green], 5 deletions[red](-)[/red]'
        >>> colorize_diff_summary("1 file changed, 5 insertions(+)")
        '1 file changed, 5 insertions[green](+)[/green]'
    """
    colored = summary_line.replace('(+)', '[green](+)[/green]')
    colored = colored.replace('(-)', '[red](-)[/red]')
    return colored


def format_diff_stat_display(stat_output: str) -> Tuple[List[str], List[str]]:
    """
    Format git diff --stat output for display with colors and alignment.

    This is a higher-level function that combines parsing and formatting.

    Args:
        stat_output: Raw output from git diff --stat

    Returns:
        Tuple of (formatted_file_lines, formatted_summary_lines)

    Examples:
        >>> output = "file.py | 5 ++---\\n 1 file changed, 2 insertions(+), 3 deletions(-)"
        >>> files, summary = format_diff_stat_display(output)
        >>> files[0]
        'file.py | 5 [green]+[/green][green]+[/green][red]-[/red][red]-[/red][red]-[/red]'
    """
    # Parse the output
    file_lines, summary_lines = parse_diff_stat_output(stat_output)

    # Get max filename length for alignment
    max_len = get_max_filename_length(file_lines)

    # Format file lines with alignment and colors
    formatted_files = []
    for filename, stats in file_lines:
        padded_filename = filename.ljust(max_len)
        colored_stats = colorize_diff_stats(stats)
        formatted_files.append(f"{padded_filename} | {colored_stats}")

    # Format summary lines with colors
    formatted_summary = [colorize_diff_summary(line) for line in summary_lines]

    return formatted_files, formatted_summary


__all__ = [
    "parse_diff_stat_output",
    "get_max_filename_length",
    "colorize_diff_stats",
    "colorize_diff_summary",
    "format_diff_stat_display",
]
