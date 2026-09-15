"""Publish a confirmed change brand by brand, reporting every outcome."""

from __future__ import annotations

from contextlib import nullcontext

from titan_cli.core.result import ClientError, ClientSuccess
from titan_cli.engine import Error, Success, WorkflowContext, WorkflowResult

from ..models.view import UIFanoutOutcome
from ..operations.fanout_operations import describe_outcomes, outcome_summary


def execute_firebase_remoteconfig_fanout_publish_step(
    ctx: WorkflowContext,
) -> WorkflowResult:
    """
    Publish the planned change to each selected brand.

    Every brand is validated with Firebase and then published on its own, and
    a failure in one brand does not stop the others: nine successful publishes
    must not be lost because the tenth project denies permission. The step
    reports what each brand did, and fails only if no brand published.

    Requires:
        ctx.firebase: An initialized FirebaseClient.

    Inputs (from ctx.data):
        firebase_fanout_plan (list[UIFanoutEntry]): From firebase_remoteconfig_fanout_plan.
        dry_run (bool, optional): Validate everywhere, publish nothing.

    Outputs (saved to ctx.data):
        firebase_fanout_outcomes (list[UIFanoutOutcome]): Per-brand results.
        firebase_fanout_published (int): Brands published.
        firebase_fanout_failed (int): Brands that failed.

    Returns:
        Success: If at least one brand published (or validated, in a dry run).
        Error: If the plan is missing or every brand failed.
    """
    if ctx.textual:
        ctx.textual.begin_step("Publicar por marca")

    if not ctx.firebase:
        return _fail(ctx, "El plugin de Firebase no está disponible")

    plan = ctx.get("firebase_fanout_plan")
    if not plan:
        return _fail(
            ctx,
            "No hay plan de publicación. Ejecuta "
            "firebase_remoteconfig_fanout_plan antes de este paso.",
        )

    dry_run = bool(ctx.get("dry_run"))
    outcomes = [_publish_one(ctx, entry, dry_run) for entry in plan]
    counts = outcome_summary(outcomes)

    if ctx.textual:
        ctx.textual.table(
            headers=["Marca", "Proyecto", "Resultado", "Detalle"],
            rows=describe_outcomes(outcomes),
            title="Resultado por marca",
            flex_column=3,
        )

    action = "validadas" if dry_run else "publicadas"
    message = f"{counts['published']} marcas {action}, {counts['failed']} con error"

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
            "firebase_fanout_outcomes": outcomes,
            "firebase_fanout_published": counts["published"],
            "firebase_fanout_failed": counts["failed"],
        },
    )


def _publish_one(
    ctx: WorkflowContext,
    entry,
    dry_run: bool,
) -> UIFanoutOutcome:
    """Validate and publish one brand, capturing the failure instead of raising."""
    validation = _run(
        ctx,
        f"Validando {entry.target.project_id}...",
        lambda: ctx.firebase.publish_remote_config_change(
            entry.target.project_id,
            entry.change,
            validate_only=True,
        ),
    )
    match validation:
        case ClientError(error_message=error_message):
            return UIFanoutOutcome(
                target=entry.target,
                error=f"validación: {error_message}",
            )

    if dry_run:
        return UIFanoutOutcome(target=entry.target, published=validation.data)

    result = _run(
        ctx,
        f"Publicando en {entry.target.project_id}...",
        lambda: ctx.firebase.publish_remote_config_change(
            entry.target.project_id,
            entry.change,
            validate_only=False,
        ),
    )
    match result:
        case ClientSuccess(data=published):
            return UIFanoutOutcome(target=entry.target, published=published)
        case ClientError(error_message=error_message):
            return UIFanoutOutcome(target=entry.target, error=error_message)

    return UIFanoutOutcome(
        target=entry.target,
        error="Respuesta inesperada al publicar",
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
