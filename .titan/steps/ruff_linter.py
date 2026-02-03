import json
import subprocess
from pathlib import Path
from titan_cli.engine.context import WorkflowContext
from titan_cli.engine.results import Success, Error, WorkflowResult
from titan_cli.engine.utils import get_poetry_venv_env
from titan_cli.ui.tui.widgets import Table


def _format_file_path(file_path: str, project_root: str) -> str:
    """Format file path relative to project root if possible."""
    try:
        project_path = Path(project_root).resolve()
        file_path_obj = Path(file_path).resolve()
        if file_path_obj.is_relative_to(project_path):
            return str(file_path_obj.relative_to(project_path))
    except (ValueError, OSError):
        pass  # Keep original path if conversion fails
    return file_path


def ruff_linter(ctx: WorkflowContext) -> WorkflowResult:
    """
    Run ruff with autofix and show diff between before/after.
    """
    if not ctx.textual:
        return Error("Textual UI context is not available for this step.")

    # Begin step container
    ctx.textual.begin_step("Run Ruff Linter")

    project_root = ctx.get("project_root", ".") # Fallback to current dir
    venv_env = get_poetry_venv_env(cwd=project_root)
    if not venv_env:
        ctx.textual.end_step("error")
        return Error("Could not determine poetry virtual environment for ruff.")

    # 1. Scan before fix
    ctx.textual.dim_text("Running initial ruff scan...")
    result_before = subprocess.run(
        ["ruff", "check", ".", "--output-format=json"],
        capture_output=True,
        text=True,
        cwd=project_root,
        env=venv_env
    )

    try:
        errors_before = json.loads(result_before.stdout) if result_before.stdout else []
    except json.JSONDecodeError:
        ctx.textual.end_step("error")
        return Error(f"Failed to parse initial ruff output as JSON.\n{result_before.stdout}")


    # 2. Auto-fix
    ctx.textual.dim_text("Applying auto-fixes...")
    subprocess.run(
        ["ruff", "check", ".", "--fix", "--quiet"],
        capture_output=True,
        cwd=project_root,
        env=venv_env
    )

    # 3. Scan after fix
    ctx.textual.dim_text("Running final ruff scan...")
    result_after = subprocess.run(
        ["ruff", "check", ".", "--output-format=json"],
        capture_output=True,
        text=True,
        cwd=project_root,
        env=venv_env
    )
    try:
        errors_after = json.loads(result_after.stdout) if result_after.stdout else []
    except json.JSONDecodeError:
        ctx.textual.end_step("error")
        return Error(f"Failed to parse final ruff output as JSON.\n{result_after.stdout}")

    # 4. Show summary
    ctx.textual.text("")  # spacing
    fixed_count = len(errors_before) - len(errors_after)

    if fixed_count > 0:
        ctx.textual.success_text(f"Auto-fixed {fixed_count} issue(s)")

    if not errors_after:
        ctx.textual.success_text("All linting issues resolved!")
        ctx.textual.end_step("success")
        return Success("Linting passed")

    # 5. Show remaining errors
    if errors_after:
        ctx.textual.warning_text(f"{len(errors_after)} issue(s) require manual fix:")
        ctx.textual.text("")  # spacing

        # Prepare data for the table
        table_headers = ["File", "Line", "Col", "Code", "Message"]
        table_rows = []

        for error in errors_after:
            file_path = _format_file_path(error.get("filename", "Unknown file"), project_root)

            location = error.get("location", {})
            row = str(location.get("row", "?"))
            col = str(location.get("column", "?"))
            code = error.get("code", "")
            message = error.get("message", "")

            table_rows.append([file_path, row, col, code, message])

        # Mount table widget
        ctx.textual.mount(
            Table(
                headers=table_headers,
                rows=table_rows,
                title="Remaining Ruff Issues"
            )
        )

        # Build formatted error list for AI assistant
        errors_text = f"{len(errors_after)} linting issues found:\n\n"
        for error in errors_after:
            file_path = _format_file_path(error.get("filename", "Unknown file"), project_root)

            location = error.get("location", {})
            errors_text += f"• {file_path}:{location.get('row', '?')}:{location.get('column', '?')} - [{error.get('code', '')}] {error.get('message', '')}\n"
            if error.get("url"):
                errors_text += f"  Docs: {error['url']}\n"

        # Return Success with errors in metadata for next step to consume
        ctx.textual.end_step("success")
        return Success(
            message=f"Linting complete: {fixed_count} auto-fixed, {len(errors_after)} need manual attention",
            metadata={"step_output": errors_text}
        )

    # All issues resolved
    ctx.textual.end_step("success")
    return Success("Linting passed - all issues resolved!")
