from pathlib import Path

from titan_cli.engine.context import WorkflowContext
from titan_cli.engine.results import Error, Success, WorkflowResult

from operations import (
    build_all_plugin_inventories,
    update_plugin_workflow_steps_pages,
    write_plugin_inventories,
    write_plugin_step_references,
)


def sync_plugin_docs(ctx: WorkflowContext) -> WorkflowResult:
    """
    Synchronize generated plugin step inventory files for documentation workflows.

    Inputs (from ctx.data):
        project_root (str, optional): Repository root path. Defaults to the current working directory.

    Outputs (saved to ctx.data):
        plugin_doc_inventory_paths (list[str]): Generated inventory JSON paths relative to the project root.
        plugin_doc_inventory_plugins (list[str]): Plugin names included in the generated inventory.

    Returns:
        Success: When all inventory files are generated successfully.
        Error: When inventory generation or validation setup fails.
    """
    if not ctx.textual:
        return Error("Textual UI context is not available for this step.")

    ctx.textual.begin_step("Sync Plugin Docs")
    repo_root = Path(ctx.get("project_root", ".")).resolve()

    with ctx.textual.loading("Building plugin docs inventory..."):
        inventories, errors = build_all_plugin_inventories(repo_root)

    if errors:
        for error in errors:
            ctx.textual.error_text(error)
        ctx.textual.end_step("error")
        return Error("Plugin docs inventory validation failed. Fix the reported issues and run sync again.")

    written_paths = write_plugin_inventories(repo_root, inventories)
    written_paths.extend(write_plugin_step_references(repo_root, inventories))
    written_paths.extend(update_plugin_workflow_steps_pages(repo_root, inventories))
    for path in written_paths:
        ctx.textual.success_text(f"Generated {path.relative_to(repo_root)}")

    ctx.textual.end_step("success")
    return Success(
        "Plugin documentation inventory generated.",
        metadata={
            "plugin_doc_inventory_paths": [str(path.relative_to(repo_root)) for path in written_paths],
            "plugin_doc_inventory_plugins": [inventory["plugin"] for inventory in inventories],
        },
    )
