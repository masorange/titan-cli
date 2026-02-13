import subprocess
from titan_cli.engine.context import WorkflowContext
from titan_cli.engine.results import Success, Error, WorkflowResult
from titan_cli.engine.utils import get_poetry_venv_env
from titan_cli.ui.tui.widgets import Table

# Import operations
from operations import (
    parse_ruff_json_output,
    build_ruff_error_table_data,
    format_ruff_errors_for_ai,
)


def ruff_linter(ctx: WorkflowContext) -> WorkflowResult:
    """
    Run ruff with autofix and show diff between before/after.
    """
    if not ctx.textual:
        return Error("Textual UI context is not available for this step.")

    # Begin step container
    ctx.textual.begin_step("Run Ruff Linter")

    project_root = ctx.get("project_root", ".")  # Fallback to current dir
    venv_env = get_poetry_venv_env(cwd=project_root)
    if not venv_env:
        ctx.textual.text("")
        ctx.textual.error_text("Could not determine poetry virtual environment for ruff")
        ctx.textual.dim_text("Make sure poetry is installed and this is a poetry project")
        ctx.textual.end_step("error")
        return Error("Could not determine poetry virtual environment for ruff.")

    # 1. Scan before fix
    ctx.textual.dim_text("Running initial ruff scan...")
    try:
        result_before = subprocess.run(
            ["ruff", "check", ".", "--output-format=json"],
            capture_output=True,
            text=True,
            cwd=project_root,
            env=venv_env
        )
    except FileNotFoundError as e:
        ctx.textual.text("")
        ctx.textual.error_text(f"Failed to run ruff: {e}")
        ctx.textual.dim_text("Make sure ruff is installed")
        ctx.textual.dim_text("Try running: poetry install")
        ctx.textual.end_step("error")
        return Error(f"ruff command not found: {e}")

    # Parse using operations
    errors_before = parse_ruff_json_output(result_before.stdout)
    if errors_before is None and result_before.returncode != 0:
        ctx.textual.text("")
        ctx.textual.error_text("Failed to parse initial ruff output as JSON")
        ctx.textual.text("")
        if result_before.stdout:
            ctx.textual.dim_text("STDOUT:")
            ctx.textual.dim_text(result_before.stdout[:500])
        if result_before.stderr:
            ctx.textual.dim_text("STDERR:")
            ctx.textual.dim_text(result_before.stderr[:500])
        ctx.textual.dim_text(f"Return code: {result_before.returncode}")
        ctx.textual.end_step("error")
        return Error("Failed to parse ruff output as JSON")

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

    # Parse using operations
    errors_after = parse_ruff_json_output(result_after.stdout)
    if errors_after is None and result_after.returncode != 0:
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

        # Build table data using operations
        table_headers, table_rows = build_ruff_error_table_data(errors_after, project_root)

        # Mount table widget
        ctx.textual.mount(
            Table(
                headers=table_headers,
                rows=table_rows,
                title="Remaining Ruff Issues"
            )
        )

        # Build formatted error list for AI assistant using operations
        errors_text = format_ruff_errors_for_ai(errors_after, project_root)

        # Return Success with errors in metadata for next step to consume
        ctx.textual.end_step("success")
        return Success(
            message=f"Linting complete: {fixed_count} auto-fixed, {len(errors_after)} need manual attention",
            metadata={"step_output": errors_text}
        )

    # All issues resolved
    ctx.textual.end_step("success")
    return Success("Linting passed - all issues resolved!")
