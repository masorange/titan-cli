import subprocess
import json
import os
from pathlib import Path
from titan_cli.engine.context import WorkflowContext
from titan_cli.engine.results import Success, Error, WorkflowResult
from titan_cli.engine.utils import get_poetry_venv_env
from titan_cli.ui.tui.widgets import Table
from titan_cli.ui.tui.icons import Icons

# Import operations
from operations import (
    parse_pytest_report_summary,
    build_failure_table_data,
    format_failures_for_ai,
)


def test_runner(ctx: WorkflowContext) -> WorkflowResult:
    """
    Run pytest using the --json-report flag and parse the structured output.
    """
    if not ctx.textual:
        return Error("Textual UI context is not available for this step.")

    # Begin step container
    ctx.textual.begin_step("Run Tests")

    project_root = ctx.get("project_root", ".")
    report_path = Path(project_root) / ".report.json"

    # Get poetry venv environment for consistency with other steps
    venv_env = get_poetry_venv_env(cwd=project_root)
    if not venv_env:
        ctx.textual.text("")
        ctx.textual.error_text("Could not determine poetry virtual environment for pytest")
        ctx.textual.dim_text("Make sure poetry is installed and this is a poetry project")
        ctx.textual.end_step("error")
        return Error("Could not determine poetry virtual environment for pytest.")

    ctx.textual.dim_text("Running tests with pytest...")

    # Run pytest with JSON report enabled, using the venv environment
    try:
        result = subprocess.run(
            ["pytest", "--json-report", f"--json-report-file={report_path}"],
            capture_output=True,
            text=True,
            cwd=project_root,
            env=venv_env
        )
    except FileNotFoundError as e:
        ctx.textual.text("")
        ctx.textual.error_text(f"Failed to run pytest: {e}")
        ctx.textual.dim_text("Make sure pytest and pytest-json-report are installed")
        ctx.textual.dim_text("Try running: poetry install")
        ctx.textual.end_step("error")
        return Error(f"pytest command not found: {e}")

    # Read the report
    if not report_path.exists():
        ctx.textual.text("")
        ctx.textual.error_text(f"Pytest JSON report not found at {report_path}")
        ctx.textual.text("")
        if result.stdout:
            ctx.textual.dim_text("STDOUT:")
            ctx.textual.dim_text(result.stdout[:500])
        if result.stderr:
            ctx.textual.dim_text("STDERR:")
            ctx.textual.dim_text(result.stderr[:500])
        ctx.textual.dim_text(f"Return code: {result.returncode}")
        ctx.textual.end_step("error")
        return Error("Pytest JSON report not found. Check pytest installation and --json-report plugin.")

    try:
        with open(report_path) as f:
            report = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        ctx.textual.end_step("error")
        return Error(f"Failed to read or parse pytest JSON report: {e}")
    finally:
        # Clean up the report file
        if os.path.exists(report_path):
            os.remove(report_path)

    ctx.textual.text("")  # spacing

    # Extract summary using operations
    summary_data = parse_pytest_report_summary(report)
    passed_count = summary_data["passed"]
    failed_count = summary_data["failed"]
    total_count = summary_data["total"]
    duration = f"{summary_data['duration']:.2f}s"

    # Show summary table
    if total_count > 0:
        ctx.textual.mount(
            Table(
                headers=["Metric", "Value"],
                rows=[
                    ["Total Tests", str(total_count)],
                    ["Passed", f"{Icons.SUCCESS} {passed_count}"],
                    ["Failed", f"{Icons.ERROR} {failed_count}"],
                    ["Duration", duration]
                ],
                title="Test Results Summary",
                full_width=False  # Compact table for summary
            )
        )
        ctx.textual.text("")  # spacing

    # Handle failures
    if failed_count == 0:
        ctx.textual.success_text("All tests passed!")
        ctx.textual.end_step("success")
        return Success("All tests passed")

    ctx.textual.warning_text(f"{failed_count} test(s) failed")
    ctx.textual.text("")  # spacing

    failures = [test for test in report.get("tests", []) if test.get("outcome") == "failed"]

    # Show failures table
    if failures:
        # Build failure rows using operations
        failure_rows = build_failure_table_data(failures, max_test_name=60, max_error=150)

        ctx.textual.mount(
            Table(
                headers=["Test", "Error"],
                rows=failure_rows,
                title="Failed Tests Details"
            )
        )
        ctx.textual.text("")  # spacing

    # Format failures for AI using operations
    failures_text = format_failures_for_ai(failures)

    ctx.textual.end_step("success")
    return Success(
        message="Tests completed with failures",
        metadata={"step_output": failures_text}
    )
