"""Read a Remote Config template and show what the project holds."""

from __future__ import annotations

from contextlib import nullcontext

from titan_cli.core.result import ClientError, ClientSuccess
from titan_cli.engine import Error, Success, WorkflowContext, WorkflowResult


def execute_firebase_remoteconfig_get_step(ctx: WorkflowContext) -> WorkflowResult:
    """
    Read the active Remote Config template for one project.

    Requires:
        ctx.firebase: An initialized FirebaseClient.

    Inputs (from ctx.data):
        firebase_project_id (str): Project to read, normally from
            `firebase_select_target`.
        project_id (str, optional): Alternative key for the same thing.

    Outputs (via result metadata):
        firebase_project_id (str): Project that was read.
        firebase_remoteconfig_etag (Optional[str]): ETag required to publish
            over this template.
        firebase_remoteconfig_version (Optional[str]): Active version number.
        firebase_remoteconfig_template (UIRemoteConfigTemplate): The template.

    Returns:
        Success: If the template is read.
        Error: If Firebase is unavailable, no project is given, or the API
            rejects the read.
    """
    if ctx.textual:
        ctx.textual.begin_step("Leer Remote Config")

    if not ctx.firebase:
        message = "El plugin de Firebase no está disponible"
        if ctx.textual:
            ctx.textual.error_text(message)
            ctx.textual.end_step("error")
        return Error(message)

    project_id = (
        ctx.get("firebase_project_id")
        or ctx.get("project_id")
        or ctx.firebase.config.default_project
    )
    if not project_id:
        message = (
            "Falta el project_id de Firebase. Ejecuta firebase_select_target "
            "antes, o configura plugins.firebase.config.default_project."
        )
        if ctx.textual:
            ctx.textual.error_text(message)
            ctx.textual.end_step("error")
        return Error(message)

    loading = (
        ctx.textual.loading(f"Leyendo Remote Config de {project_id}...")
        if ctx.textual
        else nullcontext()
    )
    with loading:
        result = ctx.firebase.get_remote_config(str(project_id))

    match result:
        case ClientSuccess(data=template):
            if ctx.textual:
                _render_summary(ctx, template)
                ctx.textual.end_step("success")
            return Success(
                f"Remote Config leído: {template.parameter_count} parámetros",
                metadata={
                    "firebase_project_id": template.project_id,
                    "firebase_remoteconfig_etag": template.etag,
                    "firebase_remoteconfig_version": (
                        template.version.version_number if template.version else None
                    ),
                    "firebase_remoteconfig_template": template,
                },
            )
        case ClientError(error_message=error_message):
            if ctx.textual:
                ctx.textual.error_text(error_message)
                ctx.textual.end_step("error")
            return Error(error_message)

    return Error("Respuesta inesperada al leer Remote Config")


def _render_summary(ctx: WorkflowContext, template) -> None:
    """Show counts plus who published the active version."""
    ctx.textual.text(
        f"{template.parameter_count} parámetros · "
        f"{len(template.conditions)} condiciones"
    )
    if template.parameter_group_names:
        ctx.textual.dim_text(
            f"Grupos: {', '.join(template.parameter_group_names)}"
        )

    version = template.version
    if version:
        details = [f"versión {version.version_number or '?'}"]
        if version.update_time:
            details.append(version.update_time)
        details.append(version.display_author)
        if version.update_origin:
            details.append(version.update_origin)
        ctx.textual.dim_text(f"Última publicación: {' · '.join(details)}")
        if version.description:
            ctx.textual.dim_text(f"Descripción: {version.description}")
