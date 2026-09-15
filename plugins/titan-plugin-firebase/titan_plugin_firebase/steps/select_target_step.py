"""Resolve the single Firebase project a workflow acts on."""

from __future__ import annotations

from titan_cli.engine import Error, Success, WorkflowContext, WorkflowResult

from ..operations.target_operations import TargetResolutionError, resolve_target


def execute_firebase_select_target_step(ctx: WorkflowContext) -> WorkflowResult:
    """
    Resolve the Firebase project to work on.

    This plugin does not map names to projects: a project ID is passed in or
    configured. A repository whose projects follow a naming scheme of its own
    resolves that itself and passes the result here.

    Inputs (from ctx.data):
        project_id (str, optional): Firebase project ID to use.
        project_label (str, optional): Friendlier name to show for it.

    Outputs (saved to ctx.data):
        firebase_project_id (str): Resolved project ID.
        firebase_target_label (str): User-facing reference for the target.

    Returns:
        Success: If a project could be resolved.
        Error: If the plugin is unavailable or nothing names a project.
    """
    if ctx.textual:
        ctx.textual.begin_step("Proyecto Firebase")

    if not ctx.firebase:
        return _fail(ctx, "El plugin de Firebase no está disponible")

    try:
        target = resolve_target(
            ctx.firebase.config,
            project_id=_text(ctx.get("project_id") or ctx.get("firebase_project_id")),
            label=_text(ctx.get("project_label")),
        )
    except TargetResolutionError as exc:
        return _fail(ctx, str(exc))

    if ctx.textual:
        ctx.textual.text(f"Proyecto: {target.reference()}")
        ctx.textual.end_step("success")

    return Success(
        f"Proyecto Firebase: {target.project_id}",
        metadata={
            "firebase_project_id": target.project_id,
            "firebase_target_label": target.reference(),
        },
    )


def _text(value: object) -> str | None:
    """Treat an empty workflow param as absent."""
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _fail(ctx: WorkflowContext, message: str) -> WorkflowResult:
    """Report an error through the UI and the result."""
    if ctx.textual:
        ctx.textual.error_text(message)
        ctx.textual.end_step("error")
    return Error(message)
