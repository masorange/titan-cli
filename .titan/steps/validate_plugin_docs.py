from pathlib import Path

from titan_cli.engine.context import WorkflowContext
from titan_cli.engine.results import Error, Success, WorkflowResult

from operations import build_all_plugin_inventories, validate_generated_inventories


def validate_plugin_docs(ctx: WorkflowContext) -> WorkflowResult:
    """
    Validate public plugin step documentation inventory and generated docs artifacts.

    Inputs (from ctx.data):
        project_root (str, optional): Repository root path. Defaults to the current working directory.

    Outputs (saved to ctx.data):
        plugin_doc_validation_checked (bool): Always set to `True` on successful validation.

    Returns:
        Success: When public step metadata, docstring conventions, and generated inventories are in sync.
        Error: When validation discovers missing docstrings, stale generated files, or metadata drift.
    """
    if not ctx.textual:
        return Error("Textual UI context is not available for this step.")

    ctx.textual.begin_step("Validate Plugin Docs")
    repo_root = Path(ctx.get("project_root", ".")).resolve()

    with ctx.textual.loading("Validating plugin docs inventory..."):
        inventories, errors = build_all_plugin_inventories(repo_root)
        errors.extend(validate_generated_inventories(repo_root, inventories))

    if errors:
        ctx.textual.warning_text(f"Found {len(errors)} plugin docs validation issue(s):")
        for error in errors:
            ctx.textual.error_text(error)
        ctx.textual.end_step("error")
        return Error("Plugin docs validation failed.")

    ctx.textual.success_text("Plugin docs inventory and generated files are in sync.")
    ctx.textual.end_step("success")
    return Success(
        "Plugin docs validation passed.",
        metadata={"plugin_doc_validation_checked": True},
    )
