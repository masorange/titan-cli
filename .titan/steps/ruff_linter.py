import json
import subprocess
from titan_cli.engine.context import WorkflowContext
from titan_cli.engine.results import Success, Error, WorkflowResult


def ruff_linter(ctx: WorkflowContext) -> WorkflowResult:
    """
    Run ruff with autofix and show diff between before/after.
    """
    if not ctx.ui:
        return Error("UI context is not available for this step.")

    project_root = ctx.get("project_root", ".") # Fallback to current dir

    # 1. Scan before fix
    ctx.ui.text.body("Running initial ruff scan...", style="dim")
    result_before = subprocess.run(
        ["poetry", "run", "ruff", "check", ".", "--output-format=json"],
        capture_output=True,
        text=True,
        cwd=project_root
    )

    try:
        errors_before = json.loads(result_before.stdout) if result_before.stdout else []
    except json.JSONDecodeError:
        return Error(f"Failed to parse initial ruff output as JSON.\n{result_before.stdout}")


    # 2. Auto-fix
    ctx.ui.text.body("Applying auto-fixes...", style="dim")
    subprocess.run(
        ["poetry", "run", "ruff", "check", ".", "--fix", "--quiet"],
        capture_output=True,
        cwd=project_root
    )

    # 3. Scan after fix
    ctx.ui.text.body("Running final ruff scan...", style="dim")
    result_after = subprocess.run(
        ["poetry", "run", "ruff", "check", ".", "--output-format=json"],
        capture_output=True,
        text=True,
        cwd=project_root
    )
    try:
        errors_after = json.loads(result_after.stdout) if result_after.stdout else []
    except json.JSONDecodeError:
        return Error(f"Failed to parse final ruff output as JSON.\n{result_after.stdout}")

    # 4. Show summary
    ctx.ui.spacer.small()
    fixed_count = len(errors_before) - len(errors_after)

    if fixed_count > 0:
        ctx.ui.text.success(f"Auto-fixed {fixed_count} issue(s)")

    if not errors_after:
        ctx.ui.text.success("All linting issues resolved!")
        return Success("Linting passed")

    # 5. Show remaining errors
    ctx.ui.text.warning(f"{len(errors_after)} issue(s) require manual fix:")
    ctx.ui.spacer.small()

    for error in errors_after:
        file_path = error.get("filename", "Unknown")
        location = error.get("location", {})
        row = location.get("row", "?")
        col = location.get("column", "?")
        code = error.get("code", "")
        message = error.get("message", "")

        ctx.ui.text.error(f"  {file_path}:{row}:{col} - [{code}] {message}")

    return Error(f"{len(errors_after)} linting issues remain")
