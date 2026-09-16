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
from ...models.mappers import map_template, map_version
from ...models.view import (
    UIAdcIdentity,
    UIRemoteConfigChangeSet,
    UIRemoteConfigPublishResult,
    UIRemoteConfigTemplate,
)
from ...operations.template_operations import (
    TemplateEditError,
    apply_change_set,
    build_change_set,
)
from ...models.values import RemoteConfigValueError
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

        message = "ADC activas con credenciales de usuario"
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

    @log_client_operation("firebase_publish_remote_config")
    def publish_change_set(
        self,
        project_id,
        change_set,
        *,
        validate_only: bool = False,
    ) -> ClientResult[UIRemoteConfigPublishResult]:
        """
        Apply a change set and publish (or validate) the template.

        The read happens here, immediately before the write, so the ETag is as
        fresh as it can be. A conflict means someone published between the two
        calls: the read-modify-write is retried once against the new template,
        which is the documented recovery and is safe because the change is
        described declaratively (key, target, value) rather than as a
        pre-rendered payload.

        Every target in the set lands in the same publish, so writing one value
        to the default and to three conditions produces one Remote Config
        version, not four.

        `change_set` and its value are positional on purpose: the logging
        decorator records keyword arguments, and a parameter value can carry
        business-sensitive content.
        """
        attempt = self._attempt_publish(project_id, change_set, validate_only)
        if isinstance(attempt, ClientError) and attempt.error_code == "ETAG_CONFLICT":
            retry = self._attempt_publish(project_id, change_set, validate_only)
            if isinstance(retry, ClientSuccess):
                return ClientSuccess(
                    data=UIRemoteConfigPublishResult(
                        project_id=retry.data.project_id,
                        validated_only=retry.data.validated_only,
                        etag=retry.data.etag,
                        version=retry.data.version,
                        change_set=retry.data.change_set,
                        retried_after_conflict=True,
                    ),
                    message=f"{retry.message} (tras reintentar por ETag)",
                )
            return retry
        return attempt

    def _attempt_publish(
        self,
        project_id: str,
        change_set: UIRemoteConfigChangeSet,
        validate_only: bool,
    ) -> ClientResult[UIRemoteConfigPublishResult]:
        """One read-modify-write cycle."""
        payload, etag, error = self.raw_template(project_id)
        if error is not None:
            return error
        if not etag:
            return ClientError(
                error_message=(
                    "Firebase no devolvió ETag en la lectura, así que no se "
                    "puede publicar sin riesgo de pisar otros cambios."
                ),
                error_code="MISSING_ETAG",
            )

        try:
            updated = apply_change_set(payload, change_set)
        except TemplateEditError as exc:
            return ClientError(
                error_message=str(exc),
                error_code="TEMPLATE_EDIT_ERROR",
                log_level="warning",
            )

        try:
            template, new_etag = self._network.put_template(
                project_id,
                updated,
                etag=etag,
                validate_only=validate_only,
            )
        except FirebaseAuthUnavailableError as exc:
            return ClientError(
                error_message=str(exc),
                error_code="ADC_UNAVAILABLE",
                details={"login_command": ADC_LOGIN_HINT},
            )
        except FirebaseApiError as exc:
            return _api_error_to_client_error(exc)

        version = map_version(template.version)
        result = UIRemoteConfigPublishResult(
            project_id=project_id.strip(),
            validated_only=validate_only,
            etag=new_etag,
            version=version,
            change_set=change_set,
        )
        message = (
            f"Plantilla validada para {project_id}"
            if validate_only
            else (
                f"Publicada la versión {result.version_number or '?'} de "
                f"{project_id}"
            )
        )
        return ClientSuccess(data=result, message=message)

    @log_client_operation("firebase_validate_change")
    def validate_change_set(
        self,
        project_id,
        key,
        new_value,
        conditions=None,
    ) -> ClientResult[UIRemoteConfigChangeSet]:
        """
        Validate a requested edit against the live template.

        `conditions` is a list with one entry per target, where None means the
        parameter's default value. Arguments are positional because the value
        can be sensitive and the logging decorator would record it as a
        keyword.
        """
        payload, _etag, error = self.raw_template(project_id)
        if error is not None:
            return error

        try:
            change_set = build_change_set(
                payload,
                key,
                new_value,
                conditions if conditions is not None else [None],
            )
        except TemplateEditError as exc:
            return ClientError(
                error_message=str(exc),
                error_code="TEMPLATE_EDIT_ERROR",
                log_level="warning",
            )
        except RemoteConfigValueError as exc:
            return ClientError(
                error_message=str(exc),
                error_code="INVALID_VALUE",
                log_level="warning",
            )

        return ClientSuccess(
            data=change_set,
            message=(
                f"Cambio validado para {key} en "
                f"{len(change_set.changes)} destino(s)"
            ),
        )

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
