"""Normalize the list of Firebase projects a multi-project change will touch."""

from __future__ import annotations

from titan_cli.engine import Error, Success, WorkflowContext, WorkflowResult

from ..operations.target_operations import (
    TargetResolutionError,
    parse_project_ids,
    resolve_targets,
)


def execute_firebase_select_targets_step(ctx: WorkflowContext) -> WorkflowResult:
    """
    Resolve several Firebase projects from a caller-supplied list.

    The list comes from outside this plugin, which is the point: a repository
    that runs one Firebase project per brand owns that mapping and publishes
    the resolved IDs (and, optionally, the names it prefers to show) before
    calling this step.

    Inputs (from ctx.data):
        project_ids (list or str, optional): Projects to target; a comma- or space-separated string is accepted.
        firebase_project_ids (list or str, optional): Same, as published by an earlier step.
        firebase_project_labels (dict, optional): project_id to label, shown instead of the raw ID.

    Outputs (saved to ctx.data):
        firebase_targets (list[FirebaseProjectTarget]): Resolved targets.
        firebase_project_ids (list[str]): Normalized, de-duplicated project IDs.

    Returns:
        Success: If at least one project was named.
        Error: If the plugin is unavailable or the list is empty.
    """
    if ctx.textual:
        ctx.textual.begin_step("Proyectos Firebase")

    if not ctx.firebase:
        return _fail(ctx, "El plugin de Firebase no está disponible")

    project_ids = parse_project_ids(ctx.get("project_ids")) or parse_project_ids(
        ctx.get("firebase_project_ids")
    )
    labels = ctx.get("firebase_project_labels")

    try:
        targets = resolve_targets(
            project_ids,
            labels if isinstance(labels, dict) else None,
        )
    except TargetResolutionError as exc:
        return _fail(ctx, str(exc))

    if ctx.textual:
        ctx.textual.table(
            headers=["Proyecto", "Etiqueta"],
            rows=[[target.project_id, target.label or "—"] for target in targets],
            title=f"{len(targets)} proyectos",
            flex_column=1,
        )
        ctx.textual.end_step("success")

    return Success(
        f"{len(targets)} proyectos Firebase",
        metadata={
            "firebase_targets": targets,
            "firebase_project_ids": [target.project_id for target in targets],
        },
    )


def _fail(ctx: WorkflowContext, message: str) -> WorkflowResult:
    """Report an error through the UI and the result."""
    if ctx.textual:
        ctx.textual.error_text(message)
        ctx.textual.end_step("error")
    return Error(message)
