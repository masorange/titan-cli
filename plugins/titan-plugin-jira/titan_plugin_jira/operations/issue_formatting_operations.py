"""
Issue Formatting Operations

Pure business logic for formatting Jira issues for display.
These functions can be used by any step and are easily testable.
"""

from typing import List, Tuple, Optional


def truncate_summary(summary: Optional[str], max_length: int = 60) -> str:
    """
    Truncate issue summary to maximum length.

    Args:
        summary: Issue summary text, or None
        max_length: Maximum length (default: 60)

    Returns:
        Truncated summary or default text

    Examples:
        >>> truncate_summary("Short summary")
        'Short summary'
        >>> truncate_summary("A" * 100, max_length=10)
        'AAAAAAAAAA'
        >>> truncate_summary(None)
        'No summary'
        >>> truncate_summary("")
        'No summary'
    """
    if not summary or not summary.strip():
        return "No summary"

    return summary[:max_length]


def format_issue_field(value: Optional[str], default: str = "Unknown") -> str:
    """
    Format an issue field value with a default fallback.

    Args:
        value: Field value, or None
        default: Default value if field is None or empty (default: "Unknown")

    Returns:
        Field value or default

    Examples:
        >>> format_issue_field("John Doe")
        'John Doe'
        >>> format_issue_field(None)
        'Unknown'
        >>> format_issue_field("", "N/A")
        'N/A'
        >>> format_issue_field(None, "Unassigned")
        'Unassigned'
    """
    if not value or not value.strip():
        return default

    return value


def build_issue_table_row(
    index: int,
    issue_key: str,
    status: Optional[str],
    summary: Optional[str],
    assignee: Optional[str],
    issue_type: Optional[str],
    priority: Optional[str],
    summary_max_length: int = 60
) -> List[str]:
    """
    Build a table row for an issue with formatted fields.

    Args:
        index: Row number (1-based)
        issue_key: Issue key (e.g., "PROJ-123")
        status: Issue status
        summary: Issue summary
        assignee: Issue assignee
        issue_type: Issue type
        priority: Issue priority
        summary_max_length: Maximum summary length (default: 60)

    Returns:
        List of formatted field values for table row

    Examples:
        >>> row = build_issue_table_row(1, "PROJ-123", "Open", "Fix bug", "Alice", "Bug", "High")
        >>> row
        ['1', 'PROJ-123', 'Open', 'Fix bug', 'Alice', 'Bug', 'High']
        >>> row = build_issue_table_row(1, "PROJ-1", None, None, None, None, None)
        >>> row
        ['1', 'PROJ-1', 'Unknown', 'No summary', 'Unassigned', 'Unknown', 'Unknown']
    """
    return [
        str(index),
        issue_key,
        format_issue_field(status, "Unknown"),
        truncate_summary(summary, summary_max_length),
        format_issue_field(assignee, "Unassigned"),
        format_issue_field(issue_type, "Unknown"),
        format_issue_field(priority, "Unknown"),
    ]


def get_issue_table_headers() -> List[str]:
    """
    Get standard headers for issue table.

    Returns:
        List of header names

    Examples:
        >>> get_issue_table_headers()
        ['#', 'Key', 'Status', 'Summary', 'Assignee', 'Type', 'Priority']
    """
    return ["#", "Key", "Status", "Summary", "Assignee", "Type", "Priority"]


def build_issue_table_data(
    issues: List[any],
    summary_max_length: int = 60
) -> Tuple[List[str], List[List[str]]]:
    """
    Build complete table data (headers + rows) for a list of issues.

    Args:
        issues: List of issue objects with attributes: key, status, summary, assignee, issue_type, priority
        summary_max_length: Maximum summary length (default: 60)

    Returns:
        Tuple of (headers, rows)

    Examples:
        >>> class Issue:
        ...     def __init__(self, key, status, summary):
        ...         self.key = key
        ...         self.status = status
        ...         self.summary = summary
        ...         self.assignee = "Alice"
        ...         self.issue_type = "Bug"
        ...         self.priority = "High"
        >>> issues = [Issue("PROJ-1", "Open", "Fix bug")]
        >>> headers, rows = build_issue_table_data(issues)
        >>> headers
        ['#', 'Key', 'Status', 'Summary', 'Assignee', 'Type', 'Priority']
        >>> len(rows)
        1
        >>> rows[0][1]
        'PROJ-1'
    """
    headers = get_issue_table_headers()
    rows = []

    for i, issue in enumerate(issues, 1):
        row = build_issue_table_row(
            index=i,
            issue_key=issue.key,
            status=getattr(issue, 'status', None),
            summary=getattr(issue, 'summary', None),
            assignee=getattr(issue, 'assignee', None),
            issue_type=getattr(issue, 'issue_type', None),
            priority=getattr(issue, 'priority', None),
            summary_max_length=summary_max_length
        )
        rows.append(row)

    return headers, rows


__all__ = [
    "truncate_summary",
    "format_issue_field",
    "build_issue_table_row",
    "get_issue_table_headers",
    "build_issue_table_data",
]
