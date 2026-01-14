import subprocess
import json
import os
from pathlib import Path
from titan_cli.engine.context import WorkflowContext
from titan_cli.engine.results import Success, Error, WorkflowResult
from titan_cli.engine.utils import get_poetry_venv_env
from titan_cli.ui.tui.widgets import Table, Panel
from titan_cli.ui.tui.icons import Icons

# Constants for display limits
MAX_TEST_NAME_LENGTH = 60
MAX_ERROR_DISPLAY_LENGTH = 150 # Increased to accommodate error_repr which can be longer


def test_runner(ctx: WorkflowContext) -> WorkflowResult:
    """
    Run pytest using the --json-report flag and parse the structured output.
    """
    if not ctx.textual:
        return Error("Textual UI context is not available for this step.")

    project_root = ctx.get("project_root", ".")
    report_path = Path(project_root) / ".report.json"

    # Get poetry venv environment for consistency with other steps
    venv_env = get_poetry_venv_env(cwd=project_root)
    if not venv_env:
        return Error("Could not determine poetry virtual environment for pytest.")

    ctx.textual.text("Running tests with pytest...", markup="dim")

    # Run pytest with JSON report enabled, using the venv environment
    result = subprocess.run(
        ["pytest", "--json-report", f"--json-report-file={report_path}"],
        capture_output=True,
        text=True,
        cwd=project_root,
        env=venv_env
    )
    
    # Read the report
    if not report_path.exists():
        return Error(f"Pytest JSON report not found at {report_path}. Pytest output:\n{result.stderr}")

    try:
        with open(report_path) as f:
            report = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        return Error(f"Failed to read or parse pytest JSON report: {e}")
    finally:
        # Clean up the report file
        if os.path.exists(report_path):
            os.remove(report_path)

    ctx.textual.text("")  # spacing

    # --- Extract Summary ---
    summary = report.get("summary", {})
    passed_count = summary.get("passed", 0)
    failed_count = summary.get("failed", 0)
    total_count = summary.get("total", passed_count + failed_count)
    duration = f"{report.get('duration', 0):.2f}s"

    # --- Show Summary Table ---
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

    # --- Handle Failures ---
    if failed_count == 0:
        ctx.textual.mount(Panel("All tests passed!", panel_type="success"))
        return Success("All tests passed")

    ctx.textual.text(f"{failed_count} test(s) failed", markup="yellow")
    ctx.textual.text("")  # spacing

    failures = [test for test in report.get("tests", []) if test.get("outcome") == "failed"]

    # --- Show Failures Table ---
    if failures:
        failure_rows = []
        for failure in failures:
            test_name = failure.get("nodeid", "Unknown Test")
            call = failure.get("call", {})
            error_repr = call.get("longrepr", "No error details")

            # Clean up test name and error message
            if len(test_name) > MAX_TEST_NAME_LENGTH:
                test_name = "..." + test_name[-(MAX_TEST_NAME_LENGTH - 3):]
            if len(error_repr) > MAX_ERROR_DISPLAY_LENGTH:
                error_repr = error_repr[:(MAX_ERROR_DISPLAY_LENGTH - 3)] + "..."

            failure_rows.append([test_name, error_repr])

        ctx.textual.mount(
            Table(
                headers=["Test", "Error"],
                rows=failure_rows,
                title="Failed Tests Details"
            )
        )
        ctx.textual.text("")  # spacing

    # --- Format Failures for AI ---
    failures_text = f"{failed_count} test(s) failed:\n\n"
    for failure in failures:
        failures_text += f"Test: {failure.get('nodeid', 'Unknown Test')}\n"
        failures_text += f"Error:\n  {failure.get('call', {}).get('longrepr', 'N/A')}\n\n"

    return Success(
        message="Tests completed with failures",
        metadata={"step_output": failures_text}
    )

