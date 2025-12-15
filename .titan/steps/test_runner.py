import subprocess
import re
from titan_cli.engine.context import WorkflowContext
from titan_cli.engine.results import Success, Error, WorkflowResult


def test_runner(ctx: WorkflowContext) -> WorkflowResult:
    """
    Run pytest and capture detailed failure information.
    Returns success with test failures in metadata for AI assistance.
    """
    if not ctx.ui:
        return Error("UI context is not available for this step.")

    project_root = ctx.get("project_root", ".")

    ctx.ui.text.body("Running tests with pytest...", style="dim")

    # Run pytest with short traceback for cleaner error messages
    result = subprocess.run(
        ["poetry", "run", "pytest", "--tb=short", "-v"],
        capture_output=True,
        text=True,
        cwd=project_root
    )

    output = result.stdout + result.stderr

    ctx.ui.spacer.small()

    # Extract test summary line (e.g., "5 failed, 10 passed in 2.34s")
    passed_count = 0
    failed_count = 0
    total_count = 0
    duration = "?"

    # Try different summary patterns
    summary_match = re.search(r"(\d+) failed.*?(\d+) passed.*?in ([\d\.]+s)", output)
    if summary_match:
        failed_count = int(summary_match.group(1))
        passed_count = int(summary_match.group(2))
        duration = summary_match.group(3)
        total_count = failed_count + passed_count
    else:
        # Try just passed
        summary_match = re.search(r"(\d+) passed.*?in ([\d\.]+s)", output)
        if summary_match:
            passed_count = int(summary_match.group(1))
            failed_count = 0
            duration = summary_match.group(2)
            total_count = passed_count

    # Show test summary table
    if ctx.ui.table and total_count > 0:
        summary_headers = ["Metric", "Value"]
        summary_rows = [
            ["Total Tests", str(total_count)],
            ["Passed", f"✓ {passed_count}"],
            ["Failed", f"✗ {failed_count}"],
            ["Duration", duration]
        ]
        ctx.ui.table.print_table(
            headers=summary_headers,
            rows=summary_rows,
            title="Test Results Summary"
        )
        ctx.ui.spacer.small()

    # Check if all tests passed
    if result.returncode == 0:
        ctx.ui.text.success("✓ All tests passed!")
        # Don't return step_output in metadata - no errors to fix
        return Success("All tests passed")

    # Tests failed - show warning
    ctx.ui.text.warning(f"{failed_count} test(s) failed")
    ctx.ui.spacer.small()

    # Parse failures - extract test names and error messages
    failures = []
    lines = output.split("\n")

    i = 0
    while i < len(lines):
        line = lines[i]

        # Look for FAILED test::name pattern
        if "FAILED " in line:
            # Extract test name
            test_name = line.split("FAILED ")[1].split(" - ")[0].strip() if "FAILED " in line else line.strip()

            # Look ahead for the error section (starts with "E   ")
            error_lines = []
            j = i + 1
            while j < len(lines) and j < i + 50:  # Look ahead max 50 lines
                if lines[j].strip().startswith("E "):
                    # This is an error line from pytest
                    error_lines.append(lines[j].strip()[2:])  # Remove "E " prefix
                elif error_lines and (lines[j].startswith("FAILED") or lines[j].startswith("=")):
                    # End of this test's error section
                    break
                j += 1

            error_msg = "\n  ".join(error_lines[:10]) if error_lines else "No error details available"

            failures.append({
                "test": test_name,
                "error": error_msg
            })

        i += 1

    # Show failures in a table
    if failures and ctx.ui.table:
        failure_headers = ["Test", "Error"]
        failure_rows = []
        for failure in failures:
            # Truncate test name if too long
            test_display = failure["test"]
            if len(test_display) > 60:
                test_display = "..." + test_display[-57:]

            # Truncate error if too long
            error_display = failure["error"]
            if len(error_display) > 100:
                error_display = error_display[:97] + "..."

            failure_rows.append([test_display, error_display])

        ctx.ui.table.print_table(
            headers=failure_headers,
            rows=failure_rows,
            title="Failed Tests Details",
            show_lines=True
        )
        ctx.ui.spacer.small()

    # Build formatted failures for AI
    if failures:
        failures_text = f"{len(failures)} test(s) failed:\n\n"
        for failure in failures:
            failures_text += f"Test: {failure['test']}\n"
            failures_text += f"Error:\n  {failure['error']}\n\n"
    else:
        # Fallback if parsing failed
        failures_text = "Tests failed but could not parse error details.\n\n"
        failures_text += f"Output:\n{output[-1000:]}"  # Last 1000 chars

    # Return Success with failures in metadata for AI assistant
    return Success(
        message="Tests completed with failures",
        metadata={"step_output": failures_text}
    )
