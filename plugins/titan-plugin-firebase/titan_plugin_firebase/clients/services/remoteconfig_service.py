"""
Remote Config data access.

Every method returns `ClientResult`, so steps never handle exceptions.

One caveat on logging: `@log_client_operation` writes every keyword argument
at DEBUG. Parameter values can carry business-sensitive content, so anything
value-bearing is passed positionally and never as a kwarg.
"""

from __future__ import annotations

from typing import Optional

from titan_cli.core.logging import log_client_operation
from titan_cli.core.result import ClientError, ClientResult, ClientSuccess

from ...exceptions import (
    FirebaseApiError,
    FirebaseAuthUnavailableError,
)
from ...models.mappers import map_template
from ...models.view import UIAdcIdentity, UIRemoteConfigTemplate
from ..network.adc_auth import ADC_LOGIN_HINT, service_account_env_var_set
from ..network.remoteconfig_network import RemoteConfigNetwork

_STATUS_ERROR_CODES = {
    400: "BAD_REQUEST",
    401: "AUTH_REJECTED",
    403: "PERMISSION_DENIED",
    404: "NOT_FOUND",
    409: "ETAG_CONFLICT",
}


def _api_error_to_client_error(exc: FirebaseApiError) -> ClientError:
    """Map an API failure to a ClientError, keeping the actionable message."""
    status = exc.status_code
    error_code = _STATUS_ERROR_CODES.get(status or 0, "API_ERROR")
    # A stale ETag and a missing project are expected outcomes a workflow
    # recovers from; only genuine failures deserve an error-level log.
    log_level = "warning" if status in {404, 409} else "error"
    return ClientError(
        error_message=str(exc),
        error_code=error_code,
        log_level=log_level,
        details={"status_code": status} if status else None,
    )


class RemoteConfigService:
    """Reads and publishes Remote Config templates for one plugin config."""

    def __init__(self, network: RemoteConfigNetwork) -> None:
        self._network = network

    @log_client_operation("firebase_check_auth")
    def check_auth(self) -> ClientResult[UIAdcIdentity]:
        """
        Verify Application Default Credentials and report the identity.

        A service-account credential is reported, not rejected: it works, but
        every publish would be attributed to the service account instead of
        the person running the workflow.
        """
        try:
            identity = self._network.adc_session.identity
        except FirebaseAuthUnavailableError as exc:
            return ClientError(
                error_message=str(exc),
                error_code="ADC_UNAVAILABLE",
                details={"login_command": ADC_LOGIN_HINT},
            )

        message = f"ADC activas para {identity.display_account}"
        if not identity.is_user_credential:
            message = (
                f"ADC activas como {identity.credential_kind} "
                f"({identity.display_account})"
            )
        return ClientSuccess(
            data=identity,
            message=message,
        )

    @log_client_operation("firebase_get_remote_config")
    def get_template(self, project_id: str) -> ClientResult[UIRemoteConfigTemplate]:
        """Read the active Remote Config template for one project."""
        try:
            template, etag = self._network.get_template(project_id)
        except FirebaseAuthUnavailableError as exc:
            return ClientError(
                error_message=str(exc),
                error_code="ADC_UNAVAILABLE",
                details={"login_command": ADC_LOGIN_HINT},
            )
        except FirebaseApiError as exc:
            return _api_error_to_client_error(exc)

        ui_template = map_template(project_id.strip(), template, etag)
        return ClientSuccess(
            data=ui_template,
            message=(
                f"{ui_template.parameter_count} parámetros y "
                f"{len(ui_template.conditions)} condiciones en {project_id}"
            ),
        )

    def uses_service_account_env_var(self) -> bool:
        """Whether GOOGLE_APPLICATION_CREDENTIALS would decide the identity."""
        return service_account_env_var_set()

    def raw_template(
        self,
        project_id: str,
    ) -> tuple[Optional[dict], Optional[str], Optional[ClientError]]:
        """
        Read the template as the exact payload the API returned, plus its ETag.

        Publishing replaces the whole template, so a write path needs the raw
        payload — the UI model is lossy by design.
        """
        try:
            template, etag = self._network.get_template(project_id)
        except FirebaseAuthUnavailableError as exc:
            return None, None, ClientError(
                error_message=str(exc),
                error_code="ADC_UNAVAILABLE",
                details={"login_command": ADC_LOGIN_HINT},
            )
        except FirebaseApiError as exc:
            return None, None, _api_error_to_client_error(exc)
        return template.to_payload(), etag, None
