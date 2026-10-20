"""Publish planned Remote Config key copies project by project."""

from __future__ import annotations

from contextlib import nullcontext

from titan_cli.core.result import ClientError, ClientSuccess
from titan_cli.engine import Error, Success, WorkflowContext, WorkflowResult

from ..models.view import UIRemoteConfigKeyCopyOutcome
from ..operations.sync_key_operations import (
    describe_key_copy_outcomes,
    key_copy_outcome_summary,
)


def execute_firebase_remoteconfig_sync_publish_step(
    ctx: WorkflowContext,
) -> WorkflowResult:
    """
    Validate and publish planned Remote Config key copies.

    Each target project is validated first, then published on its own. A
    failure in one project is reported without losing successful copies in
    other projects.

    Requires:
        ctx.firebase: An initialized FirebaseClient.

    Inputs (from ctx.data):
        firebase_copy_plan (list[UIRemoteConfigKeyCopyPlanEntry]): From firebase_remoteconfig_copy_key.
        dry_run (bool, optional): Validate everywhere, publish nothing.

    Outputs (saved to ctx.data):
        firebase_copy_outcomes (list[UIRemoteConfigKeyCopyOutcome]): Per-project results.
        firebase_copy_published (int): Projects where the key was copied.
        firebase_copy_failed (int): Projects that failed.

    Returns:
        Success: If at least one project published (or validated in a dry run).
        Error: If the plan is missing or every project failed.
    """
    if ctx.textual:
        ctx.textual.begin_step("Publicar copias por proyecto")

    if not ctx.firebase:
        return _fail(ctx, "El plugin de Firebase no está disponible")

    plan = ctx.get("firebase_copy_plan")
    if not plan:
        return _fail(
            ctx,
            "No hay plan de copia. Ejecuta firebase_remoteconfig_copy_key "
            "antes de este paso.",
        )

    dry_run = bool(ctx.get("dry_run"))
    outcomes = [_publish_one(ctx, entry, dry_run) for entry in plan]
    counts = key_copy_outcome_summary(outcomes)

    if ctx.textual:
        ctx.textual.table(
            headers=["Proyecto destino", "Resultado", "Detalle"],
            rows=describe_key_copy_outcomes(outcomes),
            title="Resultado de copia",
            flex_column=2,
        )

    action = "validados" if dry_run else "copiados"
    message = f"{counts['copied']} proyectos {action}, {counts['failed']} con error"

    if counts["copied"] == 0:
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
            "firebase_copy_outcomes": outcomes,
            "firebase_copy_published": counts["copied"],
            "firebase_copy_failed": counts["failed"],
        },
    )


def _publish_one(
    ctx: WorkflowContext,
    entry,
    dry_run: bool,
) -> UIRemoteConfigKeyCopyOutcome:
    """Validate and publish one copied key, capturing failures."""
    validation = _run(
        ctx,
        f"Validando {entry.target.project_id}...",
        lambda: ctx.firebase.copy_remote_config_key(
            entry.source.project_id,
            entry.target.project_id,
            entry.key,
            validate_only=True,
        ),
    )
    match validation:
        case ClientError(error_message=error_message):
            return UIRemoteConfigKeyCopyOutcome(
                entry=entry,
                error=f"validación: {error_message}",
            )

    if dry_run:
        return UIRemoteConfigKeyCopyOutcome(entry=entry, published=validation.data)

    result = _run(
        ctx,
        f"Publicando en {entry.target.project_id}...",
        lambda: ctx.firebase.copy_remote_config_key(
            entry.source.project_id,
            entry.target.project_id,
            entry.key,
            validate_only=False,
        ),
    )
    match result:
        case ClientSuccess(data=published):
            return UIRemoteConfigKeyCopyOutcome(entry=entry, published=published)
        case ClientError(error_message=error_message):
            return UIRemoteConfigKeyCopyOutcome(entry=entry, error=error_message)

    return UIRemoteConfigKeyCopyOutcome(
        entry=entry,
        error="Respuesta inesperada al copiar la clave",
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
