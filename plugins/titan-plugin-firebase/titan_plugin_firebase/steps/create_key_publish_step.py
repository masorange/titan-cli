"""Publish planned Remote Config key creations project by project."""

from __future__ import annotations

from contextlib import nullcontext

from titan_cli.core.result import ClientError, ClientSuccess
from titan_cli.engine import Error, Success, WorkflowContext, WorkflowResult

from ..models.view import UIRemoteConfigKeyCreateOutcome
from ..operations.create_key_operations import (
    create_outcome_summary,
    describe_create_outcomes,
)


def execute_firebase_remoteconfig_create_key_publish_step(
    ctx: WorkflowContext,
) -> WorkflowResult:
    """
    Validate and publish planned Remote Config key creations.

    Every target is validated with Firebase immediately before publishing, so
    concurrent console edits are still protected by ETag handling. A failure in
    one project is reported without stopping the remaining selected projects.

    Requires:
        ctx.firebase: An initialized FirebaseClient.

    Inputs (from ctx.data):
        firebase_create_key_plan (list[UIRemoteConfigKeyCreatePlanEntry]): From firebase_remoteconfig_create_key_plan.
        dry_run (bool, optional): Validate everywhere, publish nothing.

    Outputs (saved to ctx.data):
        firebase_create_key_outcomes (list[UIRemoteConfigKeyCreateOutcome]): Per-project results.
        firebase_create_key_published (int): Projects published.
        firebase_create_key_failed (int): Projects that failed.

    Returns:
        Success: If at least one project published (or validated in a dry run).
        Error: If the plan is missing or every project failed.
    """
    if ctx.textual:
        ctx.textual.begin_step("Crear clave por proyecto")

    if not ctx.firebase:
        return _fail(ctx, "El plugin de Firebase no está disponible")

    plan = ctx.get("firebase_create_key_plan")
    if not plan:
        return _fail(
            ctx,
            "No hay plan de creación. Ejecuta "
            "firebase_remoteconfig_create_key_plan antes de este paso.",
        )

    dry_run = bool(ctx.get("dry_run"))
    outcomes = [_publish_one(ctx, entry, dry_run) for entry in plan]
    counts = create_outcome_summary(outcomes)

    if ctx.textual:
        ctx.textual.table(
            headers=["Proyecto", "Resultado", "Detalle"],
            rows=describe_create_outcomes(outcomes),
            title="Resultado por proyecto",
            flex_column=2,
        )

    action = "validados" if dry_run else "publicados"
    message = f"{counts['published']} proyectos {action}, {counts['failed']} con error"

    if counts["published"] == 0:
        return _fail(ctx, message)

    if ctx.textual:
        if counts["failed"]:
            ctx.textual.warning_text(message)
        else:
            ctx.textual.success_text(message)
        ctx.textual.end_step("success")

    return Success(
        message,
        metadata={
            "firebase_create_key_outcomes": outcomes,
            "firebase_create_key_published": counts["published"],
            "firebase_create_key_failed": counts["failed"],
        },
    )


def _publish_one(
    ctx: WorkflowContext,
    entry,
    dry_run: bool,
) -> UIRemoteConfigKeyCreateOutcome:
    """Validate and publish one project, capturing failures instead of raising."""
    validation = _run(
        ctx,
        f"Validando creación en {entry.target.project_id}...",
        lambda: ctx.firebase.create_remote_config_key(
            entry.target.project_id,
            entry.request,
            validate_only=True,
        ),
    )
    match validation:
        case ClientError(error_message=error_message):
            return UIRemoteConfigKeyCreateOutcome(
                entry=entry,
                error=f"validación: {error_message}",
            )

    if dry_run:
        return UIRemoteConfigKeyCreateOutcome(
            entry=entry,
            published=validation.data,
        )

    result = _run(
        ctx,
        f"Publicando creación en {entry.target.project_id}...",
        lambda: ctx.firebase.create_remote_config_key(
            entry.target.project_id,
            entry.request,
            validate_only=False,
        ),
    )
    match result:
        case ClientSuccess(data=published):
            return UIRemoteConfigKeyCreateOutcome(
                entry=entry,
                published=published,
            )
        case ClientError(error_message=error_message):
            return UIRemoteConfigKeyCreateOutcome(
                entry=entry,
                error=error_message,
            )

    return UIRemoteConfigKeyCreateOutcome(
        entry=entry,
        error="Respuesta inesperada al crear la clave.",
    )


def _run(ctx: WorkflowContext, message: str, call):
    """Run a client call under a spinner when the TUI is present."""
    loading = ctx.textual.loading(message) if ctx.textual else nullcontext()
    with loading:
        return call()


def _fail(ctx: WorkflowContext, message: str) -> WorkflowResult:
    """Report an error through the UI and the result."""
    if ctx.textual:
        ctx.textual.error_text(message)
        ctx.textual.end_step("error")
    return Error(message)
