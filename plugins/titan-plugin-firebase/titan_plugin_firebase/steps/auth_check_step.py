"""Verify Application Default Credentials before touching Remote Config."""

from __future__ import annotations

from titan_cli.core.result import ClientError, ClientSuccess
from titan_cli.engine import Error, Success, WorkflowContext, WorkflowResult

from ..clients.network.adc_auth import ADC_LOGIN_HINT


def execute_firebase_auth_check_step(ctx: WorkflowContext) -> WorkflowResult:
    """
    Check that Google Application Default Credentials are usable.

    Requires:
        ctx.firebase: An initialized FirebaseClient.

    Outputs (saved to ctx.data):
        firebase_account (Optional[str]): Service account email, when applicable.
        firebase_credential_kind (str): user, service_account, impersonated, ...
        firebase_credential_is_user (bool): Whether publishes get a real author.

    Returns:
        Success: If credentials resolve and can mint a token.
        Error: If no ADC session exists or it cannot be refreshed.
    """
    if ctx.textual:
        ctx.textual.begin_step("Verificar credenciales de Google")

    if not ctx.firebase:
        message = "El plugin de Firebase no está disponible"
        if ctx.textual:
            ctx.textual.error_text(message)
            ctx.textual.end_step("error")
        return Error(message)

    with _loading(ctx, "Resolviendo Application Default Credentials..."):
        result = ctx.firebase.check_auth()

    match result:
        case ClientSuccess(data=identity, message=message):
            if ctx.textual:
                ctx.textual.success_text(message)
                if identity.is_user_credential:
                    # Titan cannot read the signed-in email (an ADC token for
                    # cloud-platform need not carry the userinfo scope), and
                    # the authoritative answer is the one Firebase records on
                    # the published version anyway.
                    ctx.textual.dim_text(
                        "Firebase registrará tu cuenta de Google como autora "
                        "de cada publicación."
                    )
                if identity.quota_project_id:
                    ctx.textual.dim_text(
                        f"Proyecto de cuota: {identity.quota_project_id}"
                    )
                _warn_about_attribution(ctx, identity)
                ctx.textual.end_step("success")
            return Success(
                message,
                metadata={
                    "firebase_account": identity.account,
                    "firebase_credential_kind": identity.credential_kind,
                    "firebase_credential_is_user": identity.is_user_credential,
                },
            )
        case ClientError(error_message=error_message):
            if ctx.textual:
                ctx.textual.error_text(error_message)
                ctx.textual.dim_text(f"Ejecuta: {ADC_LOGIN_HINT}")
                ctx.textual.end_step("error")
            return Error(error_message)

    return Error("Respuesta inesperada al verificar las credenciales")


def _warn_about_attribution(ctx: WorkflowContext, identity) -> None:
    """
    Warn when the audit trail would not name a person.

    Firebase attributes every published version to the identity behind the
    token. A service account turns "who changed this flag" into the same
    answer for the whole team, which is exactly what the version history is
    for, so this is worth saying before anyone writes.
    """
    if identity.is_user_credential:
        return

    ctx.textual.warning_text(
        f"Las credenciales son de tipo {identity.credential_kind}: las "
        "publicaciones aparecerán a su nombre en el historial de Firebase, "
        "no al de quien ejecuta el workflow."
    )
    if ctx.firebase.uses_service_account_env_var():
        ctx.textual.dim_text(
            "GOOGLE_APPLICATION_CREDENTIALS está definida. Quítala para usar "
            f"tu cuenta personal: {ADC_LOGIN_HINT}"
        )


def _loading(ctx: WorkflowContext, message: str):
    """Show a spinner when running inside the TUI."""
    from contextlib import nullcontext

    if ctx.textual:
        return ctx.textual.loading(message)
    return nullcontext()
