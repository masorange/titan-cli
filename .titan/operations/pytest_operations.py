"""
Pytest Operations

Pure business logic for pytest test runner functionality.
These functions can be used by any step and are easily testable.
"""

from typing import Dict, List, Any


def parse_pytest_report_summary(report: Dict) -> Dict[str, Any]:
    """
    Extract summary data from pytest JSON report.

    Args:
        report: Pytest JSON report dict

    Returns:
        Dict with passed, failed, total, and duration

    Examples:
        >>> report = {"summary": {"passed": 5, "failed": 2}, "duration": 1.5}
        >>> result = parse_pytest_report_summary(report)
        >>> result["passed"]
        5
        >>> result["failed"]
        2
    """
    summary = report.get("summary", {})
    passed_count = summary.get("passed", 0)
    failed_count = summary.get("failed", 0)
    total_count = summary.get("total", passed_count + failed_count)
    duration = report.get("duration", 0)

    return {
        "passed": passed_count,
        "failed": failed_count,
        "total": total_count,
        "duration": duration,
    }


def truncate_text(text: str, max_length: int) -> str:
    """
    Truncate text to maximum length with ellipsis.

    Args:
        text: Text to truncate
        max_length: Maximum length including ellipsis

    Returns:
        Truncated text or original if shorter

    Examples:
        >>> truncate_text("Hello world", 8)
        'Hello...'
        >>> truncate_text("Hi", 10)
        'Hi'
    """
    if len(text) <= max_length:
        return text
    return text[:(max_length - 3)] + "..."


def build_failure_table_data(
    failures: List[Dict],
    max_test_name: int = 60,
    max_error: int = 150
) -> List[List[str]]:
    """
    Build table rows from pytest failures.

    Args:
        failures: List of failed test dicts
        max_test_name: Maximum length for test name
        max_error: Maximum length for error message

    Returns:
        List of table rows [test_name, error]

    Examples:
        >>> failures = [{"nodeid": "test_foo.py::test_bar", "call": {"longrepr": "AssertionError"}}]
        >>> rows = build_failure_table_data(failures)
        >>> len(rows)
        1
        >>> rows[0][0]
        'test_foo.py::test_bar'
    """
    failure_rows = []

    for failure in failures:
        test_name = failure.get("nodeid", "Unknown Test")
        call = failure.get("call", {})
        error_repr = call.get("longrepr", "No error details")

        # Clean up test name and error message
        if len(test_name) > max_test_name:
            test_name = "..." + test_name[-(max_test_name - 3):]
        if len(error_repr) > max_error:
            error_repr = error_repr[:(max_error - 3)] + "..."

        failure_rows.append([test_name, error_repr])

    return failure_rows


def format_failures_for_ai(failures: List[Dict]) -> str:
    """
    Format test failures as text for AI consumption.

    Args:
        failures: List of failed test dicts

    Returns:
        Formatted text with failure details

    Examples:
        >>> failures = [{"nodeid": "test_foo", "call": {"longrepr": "Error"}}]
        >>> result = format_failures_for_ai(failures)
        >>> "test_foo" in result
        True
    """
    failures_text = f"{len(failures)} test(s) failed:\n\n"

    for failure in failures:
        failures_text += f"Test: {failure.get('nodeid', 'Unknown Test')}\n"
        failures_text += f"Error:\n  {failure.get('call', {}).get('longrepr', 'N/A')}\n\n"

    return failures_text


__all__ = [
    "parse_pytest_report_summary",
    "build_failure_table_data",
    "format_failures_for_ai",
    "truncate_text",
]
