"""Resolve the single Firebase project a workflow acts on."""

from __future__ import annotations

from titan_cli.engine import Error, Success, WorkflowContext, WorkflowResult

from ..operations.target_operations import TargetResolutionError, resolve_target
from .project_prompts import ask_project_id


def execute_firebase_select_target_step(ctx: WorkflowContext) -> WorkflowResult:
    """
    Resolve the Firebase project to work on.

    A project ID can be passed directly or configured. If the ID appears in a
    configured project set, generic metadata such as brand and environment is
    carried forward for later steps.

    Inputs (from ctx.data):
        project_id (str, optional): Firebase project ID to use.
        firebase_project_id (str, optional): Same value, as emitted by earlier steps.
        project_label (str, optional): Friendlier name to show for it.
        project_brand (str, optional): Brand metadata supplied by an earlier step.
        environment (str, optional): Environment metadata supplied by the workflow.
        firebase_environment (str, optional): Same environment, as emitted by earlier steps.
        project_filter (str, optional): Case-insensitive words used to filter the TUI project catalogue.
        firebase_project_filter (str, optional): Same filter, as emitted by earlier steps.

    Outputs (saved to ctx.data):
        firebase_project_id (str): Resolved project ID.
        firebase_target_label (str): User-facing reference for the target.
        firebase_environment (str, optional): Resolved environment, when known.
        firebase_project_brand (str, optional): Resolved brand, when known.

    Returns:
        Success: If a project could be resolved.
        Error: If the plugin is unavailable or nothing names a project.
    """
    if ctx.textual:
        ctx.textual.begin_step("Proyecto Firebase")

    if not ctx.firebase:
        return _fail(ctx, "El plugin de Firebase no está disponible")

    project_id = _text(ctx.get("project_id") or ctx.get("firebase_project_id"))
    if (
        project_id is None
        and ctx.firebase.config.default_project is None
        and ctx.textual
    ):
        project_id = ask_project_id(ctx)
        if project_id is None:
            return _fail(
                ctx,
                "No se indicó ningún project_id de Firebase.",
            )

    try:
        target = resolve_target(
            ctx.firebase.config,
            project_id=project_id,
            label=_text(ctx.get("project_label")),
            brand=_text(ctx.get("project_brand")),
            environment=_text(ctx.get("environment"))
            or _text(ctx.get("firebase_environment")),
        )
    except TargetResolutionError as exc:
        return _fail(ctx, str(exc))

    if ctx.textual:
        ctx.textual.text(f"Proyecto: {target.reference()}")
        if target.environment:
            ctx.textual.dim_text(f"Entorno: {target.environment.upper()}")
        if target.brand:
            ctx.textual.dim_text(f"Marca: {target.brand}")
        ctx.textual.end_step("success")

    metadata = {
        "firebase_project_id": target.project_id,
        "firebase_target_label": target.reference(),
    }
    if target.environment:
        metadata["firebase_environment"] = target.environment
    if target.brand:
        metadata["firebase_project_brand"] = target.brand

    return Success(
        f"Proyecto Firebase: {target.project_id}",
        metadata=metadata,
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
