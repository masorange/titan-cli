"""Validate and publish a confirmed Remote Config change."""

from __future__ import annotations

from contextlib import nullcontext

from titan_cli.core.result import ClientError, ClientSuccess
from titan_cli.engine import Error, Success, WorkflowContext, WorkflowResult


def execute_firebase_remoteconfig_publish_step(
    ctx: WorkflowContext,
) -> WorkflowResult:
    """
    Publish one confirmed change, validating it with Firebase first.

    The template is read again inside the client immediately before the write,
    so the ETag is fresh even if the user spent time reviewing the diff, and a
    concurrent publish is retried once instead of overwritten.

    Requires:
        ctx.firebase: An initialized FirebaseClient.

    Inputs (from ctx.data):
        firebase_project_id (str): Target project.
        firebase_change (UIRemoteConfigChange): The change to publish.
        firebase_change_confirmed (bool): Set by `firebase_remoteconfig_diff`.
        dry_run (bool, optional): Validate only, publish nothing.

    Outputs (via result metadata):
        firebase_published_version (Optional[str]): New version number.
        firebase_published_author (Optional[str]): Author Firebase recorded.
        firebase_publish_result (UIRemoteConfigPublishResult): Full outcome.

    Returns:
        Success: If Firebase validated (dry run) or published the template.
        Error: If inputs are missing, the change was never confirmed, or the
            API rejected the write.
    """
    if ctx.textual:
        ctx.textual.begin_step("Publicar en Remote Config")

    if not ctx.firebase:
        return _fail(ctx, "El plugin de Firebase no está disponible")

    change = ctx.get("firebase_change")
    project_id = ctx.get("firebase_project_id") or ctx.get("project_id")
    if change is None or not project_id:
        return _fail(
            ctx,
            "Falta el cambio o el proyecto. Ejecuta "
            "firebase_remoteconfig_set_value antes de este paso.",
        )

    dry_run = bool(ctx.get("dry_run"))
    if not dry_run and not ctx.get("firebase_change_confirmed"):
        # Publishing is the one irreversible-ish action here, so it requires
        # the explicit confirmation the diff step produces.
        return _fail(
            ctx,
            "El cambio no está confirmado. Ejecuta firebase_remoteconfig_diff "
            "antes de publicar, o pasa dry_run para solo validar.",
        )

    validation = _run(
        ctx,
        "Validando la plantilla con Firebase...",
        lambda: ctx.firebase.publish_remote_config_change(
            str(project_id),
            change,
            validate_only=True,
        ),
    )
    match validation:
        case ClientError(error_message=error_message):
            return _fail(ctx, f"Firebase rechazó la validación: {error_message}")

    if ctx.textual:
        ctx.textual.success_text("Validación correcta")

    if dry_run:
        if ctx.textual:
            ctx.textual.dim_text("dry_run activo: no se publica nada.")
            ctx.textual.end_step("success")
        return Success(
            f"Cambio validado (sin publicar) en {project_id}",
            metadata={
                "firebase_published_version": None,
                "firebase_published_author": None,
                "firebase_publish_result": validation.data,
            },
        )

    result = _run(
        ctx,
        f"Publicando en {project_id}...",
        lambda: ctx.firebase.publish_remote_config_change(
            str(project_id),
            change,
            validate_only=False,
        ),
    )

    match result:
        case ClientSuccess(data=published, message=message):
            if ctx.textual:
                _render_outcome(ctx, published)
                ctx.textual.end_step("success")
            return Success(
                message,
                metadata={
                    "firebase_published_version": published.version_number,
                    "firebase_published_author": (
                        published.version.update_user_email
                        if published.version
                        else None
                    ),
                    "firebase_publish_result": published,
                },
            )
        case ClientError(error_message=error_message):
            return _fail(ctx, error_message)

    return _fail(ctx, "Respuesta inesperada al publicar")


def _render_outcome(ctx: WorkflowContext, published) -> None:
    """Show the version Firebase created and who it attributed it to."""
    version = published.version
    ctx.textual.success_text(
        f"Publicada la versión {published.version_number or '?'}"
    )
    if version:
        # The author is the audit trail: it comes from the identity behind the
        # ADC token, so it should match whoever ran the workflow.
        details = [version.display_author]
        if version.update_origin:
            details.append(version.update_origin)
        if version.update_time:
            details.append(version.update_time)
        ctx.textual.dim_text(" · ".join(details))
        if version.description:
            ctx.textual.dim_text(version.description)
    if published.retried_after_conflict:
        ctx.textual.warning_text(
            "Alguien publicó mientras revisabas: el cambio se reaplicó sobre "
            "la plantilla nueva."
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
